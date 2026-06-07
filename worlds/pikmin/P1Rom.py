"""
P1Rom.py - Pikmin 1 patch file generation and ISO patching

DOL patch summary
-----------------
Hook at 0x800EB3D4 (stw r0, 0x042C(r6)) replaced by b -> stub at 0x8010CCE8.

Stub (14 instrs = 56 bytes, fits in 60-byte cave):
  - Reads color ID from r29 + 0x0428 (stable across all sessions)
  - Stores r29 (onion base) to fixed slot per color (0x803D7010/14/18)
  - Executes original stw r0, 0x042C(r6)
  - Returns to 0x800EB3D8

Color IDs at r29 + 0x0428 (PAL GP1P01):
    Red    = 0x0001
    Yellow = 0x0002
    Blue   = 0x0000

Fixed RAM (BSS, zeroed at boot):
    0x803D7010 : red    onion base (r29) — client computes dyn_addr = base + 0x042C
    0x803D7014 : yellow onion base (r29)
    0x803D7018 : blue   onion base (r29)
"""

import json
import struct
import zipfile

from NetUtils import convert_to_base_types
from worlds.Files import APPlayerContainer

GAME_NAME         = "Pikmin"
PATCH_FILE_ENDING = ".appik1"
VALID_GAME_ID          = b"GPIP01"
PATCHED_GAME_ID_PREFIX = b"P1P"

DOL_ISO_OFFSET        = 0x0001DA00
DOL_TEXT1_FILE_OFFSET = 0x00002520
DOL_TEXT1_RAM_ADDR    = 0x800055C0

HOOK_RAM_ADDR = 0x800EB3D4
HOOK_FILE_OFF = DOL_TEXT1_FILE_OFFSET + (HOOK_RAM_ADDR - DOL_TEXT1_RAM_ADDR)
HOOK_ISO_OFF  = DOL_ISO_OFFSET + HOOK_FILE_OFF


CAVE_RAM_ADDR = 0x8010CCE8
CAVE_FILE_OFF = DOL_TEXT1_FILE_OFFSET + (CAVE_RAM_ADDR - DOL_TEXT1_RAM_ADDR)
CAVE_ISO_OFF  = DOL_ISO_OFFSET + CAVE_FILE_OFF

# Fixed RAM: onion base pointers per color
FIXED_RED_BASE_ADDR    = 0x803D7010
FIXED_YELLOW_BASE_ADDR = 0x803D7014
FIXED_BLUE_BASE_ADDR   = 0x803D7018

# Offset within onion object to dynamic pikmin address
ONION_DYN_OFFSET = 0x042C

# Color IDs at r29 + 0x0428 (stable across all sessions, PAL GP1P01)
ONION_ID_RED    = 0x0001
ONION_ID_YELLOW = 0x0002
ONION_ID_BLUE   = 0x0000

HOOK_EXPECTED = bytes.fromhex("9006042c")
CAVE_EXPECTED = bytes.fromhex("4e800020")

def _pack(v: int) -> bytes:
    return struct.pack(">I", v & 0xFFFFFFFF)

def ppc_lis(rd, imm):      return _pack((15 << 26) | (rd << 21) | (imm & 0xFFFF))
def ppc_addi(rd, ra, imm): return _pack((14 << 26) | (rd << 21) | (ra << 16) | (imm & 0xFFFF))
def ppc_lhz(rd, ra, off):  return _pack((40 << 26) | (rd << 21) | (ra << 16) | (off & 0xFFFF))
def ppc_stw(rs, ra, off):  return _pack((36 << 26) | (rs << 21) | (ra << 16) | (off & 0xFFFF))
def ppc_cmpwi(ra, imm):    return _pack((11 << 26) | (ra << 16) | (imm & 0xFFFF))
def ppc_bne(off):          return _pack((16 << 26) | (4 << 21) | (2 << 16) | (off & 0xFFFC))
def ppc_b(fr, to):         return _pack((18 << 26) | ((to - fr) & 0x03FFFFFC))


def build_stub() -> bytes:
    """
    14-instruction stub (56 bytes) at CAVE_RAM_ADDR.
    Hooks 0x800EB3D4 (stw r0, 0x042C(r6)) — retrait pikmin.
    Stores r29 per color, executes original stw, returns.
    """
    base = CAVE_RAM_ADDR
    hi   = (FIXED_RED_BASE_ADDR >> 16) & 0xFFFF

    stub  = ppc_lhz(7, 29, 0x0428)
    stub += ppc_lis(8, hi)
    stub += ppc_cmpwi(7, ONION_ID_RED)
    stub += ppc_bne(12)
    stub += ppc_addi(10, 8, FIXED_RED_BASE_ADDR & 0xFFFF)
    stub += ppc_b(base + 0x14, base + 0x2C)
    stub += ppc_cmpwi(7, ONION_ID_YELLOW)
    stub += ppc_bne(12)
    stub += ppc_addi(10, 8, FIXED_YELLOW_BASE_ADDR & 0xFFFF)
    stub += ppc_b(base + 0x24, base + 0x2C)
    stub += ppc_addi(10, 8, FIXED_BLUE_BASE_ADDR & 0xFFFF)
    stub += ppc_stw(29, 10, 0)
    stub += ppc_stw(0, 6, 0x042C)
    stub += ppc_b(base + 0x34, HOOK_RAM_ADDR + 4)

    assert len(stub) == 56, f"Stub size: {len(stub)}"
    return stub


class InvalidISOError(Exception):
    pass


def verify_iso(iso_path: str) -> None:
    with open(iso_path, "rb") as f:
        game_id = f.read(6)
        if game_id.startswith(PATCHED_GAME_ID_PREFIX):
            raise InvalidISOError(
                "This ISO has already been patched. "
                "Please use a clean (unmodified) Pikmin 1 PAL ISO."
            )
        if game_id != VALID_GAME_ID:
            raise InvalidISOError(
                f"Invalid game ID: {game_id!r} (expected {VALID_GAME_ID!r}).\n"
                "Please provide a Pikmin 1 PAL ISO (GP1P01)."
            )
        f.seek(HOOK_ISO_OFF)
        hook_bytes = f.read(4)
        if hook_bytes != HOOK_EXPECTED:
            raise InvalidISOError(
                f"Unexpected bytes at hook location 0x{HOOK_ISO_OFF:08x}: {hook_bytes.hex()}\n"
                f"Expected {HOOK_EXPECTED.hex()}. Is this the correct ISO?"
            )
        f.seek(CAVE_ISO_OFF)
        cave_bytes = f.read(4)
        if cave_bytes != CAVE_EXPECTED:
            raise InvalidISOError(
                f"Unexpected bytes at stub cave 0x{CAVE_ISO_OFF:08x}: {cave_bytes.hex()}\n"
                f"Expected {CAVE_EXPECTED.hex()} (blr). The ISO may be modified."
            )



def patch_iso(iso_path: str, seed: str = "") -> None:
    stub   = build_stub()
    branch = ppc_b(HOOK_RAM_ADDR, CAVE_RAM_ADDR)

    suffix = (seed[-3:] if len(seed) >= 3 else seed.ljust(3, "0")).encode("ascii")
    new_game_id = PATCHED_GAME_ID_PREFIX + suffix

    with open(iso_path, "r+b") as f:
        f.seek(CAVE_ISO_OFF)
        f.write(stub)
        f.seek(HOOK_ISO_OFF)
        f.write(branch)
        f.seek(0)
        f.write(new_game_id)


class P1PlayerContainer(APPlayerContainer):
    game = GAME_NAME
    patch_file_ending = PATCH_FILE_ENDING
    compression_method = zipfile.ZIP_DEFLATED

    def __init__(self, output_data, patch_path, player_name, player, server=""):
        self.output_data = output_data
        super().__init__(patch_path, player, player_name, server)

    def write_contents(self, opened_zipfile: zipfile.ZipFile) -> None:
        opened_zipfile.writestr(
            "patch.appik1",
            json.dumps(self.output_data, indent=4, default=convert_to_base_types),
        )
        super().write_contents(opened_zipfile)