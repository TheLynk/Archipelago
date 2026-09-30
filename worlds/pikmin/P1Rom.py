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

PAL_GAME_ID  = b"GPIP01"
NTSC_GAME_ID = b"GPIE01"
SUPPORTED_GAME_IDS = (PAL_GAME_ID, NTSC_GAME_ID)

# Game ID prefix written into the patched ISO. It also acts as a version marker:
# once patched, the ISO no longer says whether it came from PAL or NTSC, and the
# client needs to know in order to pick the right memory addresses.
# PAL keeps "P1P" (compatible with already-patched ISOs).
PATCHED_PREFIX_BY_VERSION = {
    PAL_GAME_ID:  b"P1P",
    NTSC_GAME_ID: b"P1E",
}
# Patched prefix -> original Game ID, for the client.
BASE_ID_BY_PATCHED_PREFIX = {v: k for k, v in PATCHED_PREFIX_BY_VERSION.items()}

VERSION_LABELS = {
    PAL_GAME_ID:  "PAL (Europe)",
    NTSC_GAME_ID: "NTSC-U (USA)",
}

# Reference dumps (Redump.info, status "Verified"), shown in error messages to
# help the player find the right ISO. Informational only: validation is done
# through the Game ID and the patch site bytes.
EXPECTED_ISOS = {
    PAL_GAME_ID:  ("Pikmin 1 GameCube (PAL) .iso file",
                   "40c46bd6921e55558e9838930a9ffd2179802b4f"),
    NTSC_GAME_ID: ("Pikmin 1 GameCube (USA) (Rev 1) .iso file",
                   "23a153cb225fef488f57073e76df0de26789c218"),
}


def iso_sha1(path: str) -> str:
    """Return the SHA-1 of a file (read in chunks; takes a few seconds for 1.4 GB)."""
    import hashlib
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def expected_iso_help(path: str = "") -> str:
    """Help text appended to ISO errors: supported ISOs plus the file's SHA-1."""
    lines = ["", "Supported ISOs (Redump.info status: Verified):"]
    for gid, (label, sha1) in EXPECTED_ISOS.items():
        lines.append(f"  {label} | ID: {gid.decode()} | SHA-1: {sha1}")
    if path:
        try:
            lines.append(f"Your file SHA-1: {iso_sha1(path)}")
        except Exception as e:
            lines.append(f"Your file SHA-1: could not be computed ({e})")
    return "\n".join(lines)

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

# ---------------------------------------------------------------------------
# NTSC-U (GPIE01)
#
# Everything above is the PAL path. The values below come from the
# projectPiki/pikmin decomp:
#   - exitPiki__8GoalItem is 0x27C bytes in BOTH versions (identical code), and
#     the PAL hook sits at +0x1E0 from its start:
#         PAL  0x800EB1F4 + 0x1E0 = 0x800EB3D4
#         NTSC 0x800EB33C + 0x1E0 = 0x800EB51C
#   - the PAL scratch RAM is workString__3zen+0x2B0, a 1 KB .bss buffer; the
#     same symbol is at 0x803D1EE0 in NTSC, hence +0x2B0 = 0x803D2190.
# The code cave is NOT hardcoded: unlike PAL, the PAL address 0x8010CCE8 holds
# a real function in NTSC, so a free area is searched in the DOL at patch time
# (see find_code_cave).
# ---------------------------------------------------------------------------

NTSC_HOOK_RAM_ADDR = 0x800EB51C

NTSC_FIXED_RED_BASE_ADDR    = 0x803D2190
NTSC_FIXED_YELLOW_BASE_ADDR = 0x803D2194
NTSC_FIXED_BLUE_BASE_ADDR   = 0x803D2198

# Stub size, and the margin required when searching for a free area.
STUB_SIZE = 56
CAVE_MIN_SIZE = 60


def _u32(f, offset: int) -> int:
    f.seek(offset)
    return struct.unpack(">I", f.read(4))[0]


def read_game_id(iso_path: str) -> bytes:
    with open(iso_path, "rb") as f:
        return f.read(6)


def dol_text_sections(f) -> list[tuple[int, int, int]]:
    """Return the DOL .text sections as [(ISO file offset, RAM address, size)].

    The DOL location is read from the disc header (0x420) instead of being
    hardcoded, which makes the function version-independent.
    """
    dol_off = _u32(f, 0x420)
    sections = []
    for i in range(7):  # 7 sections .text
        file_off = _u32(f, dol_off + 0x00 + i * 4)
        ram_addr = _u32(f, dol_off + 0x48 + i * 4)
        size     = _u32(f, dol_off + 0x90 + i * 4)
        if file_off and size:
            sections.append((dol_off + file_off, ram_addr, size))
    return sections


def ram_to_iso_offset(f, ram_addr: int) -> int:
    """Convert a RAM address to an ISO offset using the DOL header."""
    for file_off, sec_ram, size in dol_text_sections(f):
        if sec_ram <= ram_addr < sec_ram + size:
            return file_off + (ram_addr - sec_ram)
    raise InvalidISOError(
        f"RAM address 0x{ram_addr:08X} not found in the DOL .text sections."
    )


def find_code_cave(f, min_size: int = CAVE_MIN_SIZE) -> tuple[int, int]:
    """Find a long enough run of zero bytes in the DOL .text.

    Returns (RAM address, ISO offset). The address is internal to the patch
    (the hook jumps there and the stub returns from it); the client does not need it.
    """
    for file_off, ram_addr, size in dol_text_sections(f):
        f.seek(file_off)
        data = f.read(size)
        run_start = None
        for i in range(0, len(data) - 3, 4):
            if data[i:i + 4] == b"\x00\x00\x00\x00":
                if run_start is None:
                    run_start = i
                elif i + 4 - run_start >= min_size:
                    # 4-byte alignment is already guaranteed by the loop step
                    return ram_addr + run_start, file_off + run_start
            else:
                run_start = None
    raise InvalidISOError(
        f"No free {min_size}-byte area found in the DOL. "
        "This ISO may already be modified."
    )

def _pack(v: int) -> bytes:
    return struct.pack(">I", v & 0xFFFFFFFF)

def ppc_lis(rd, imm):      return _pack((15 << 26) | (rd << 21) | (imm & 0xFFFF))
def ppc_addi(rd, ra, imm): return _pack((14 << 26) | (rd << 21) | (ra << 16) | (imm & 0xFFFF))
def ppc_lhz(rd, ra, off):  return _pack((40 << 26) | (rd << 21) | (ra << 16) | (off & 0xFFFF))
def ppc_stw(rs, ra, off):  return _pack((36 << 26) | (rs << 21) | (ra << 16) | (off & 0xFFFF))
def ppc_cmpwi(ra, imm):    return _pack((11 << 26) | (ra << 16) | (imm & 0xFFFF))
def ppc_bne(off):          return _pack((16 << 26) | (4 << 21) | (2 << 16) | (off & 0xFFFC))
def ppc_b(fr, to):         return _pack((18 << 26) | ((to - fr) & 0x03FFFFFC))


def build_stub(cave_addr: int = CAVE_RAM_ADDR,
               hook_addr: int = HOOK_RAM_ADDR,
               red_addr: int = FIXED_RED_BASE_ADDR,
               yellow_addr: int = FIXED_YELLOW_BASE_ADDR,
               blue_addr: int = FIXED_BLUE_BASE_ADDR) -> bytes:
    """
    14-instruction stub (56 bytes) at cave_addr.
    Hooks `stw r0, 0x042C(r6)` in exitPiki__8GoalItem (pikmin removal).
    Stores r29 per color, executes the original stw, returns.

    Defaults are the PAL values: called without arguments, this produces the
    PAL stub.
    """
    base = cave_addr
    hi   = (red_addr >> 16) & 0xFFFF

    # The three slots are addressed through a single `lis` followed by `addi`.
    # `addi` sign-extends its 16-bit immediate: if the low half reached 0x8000,
    # the computed address would be off by 0x10000.
    for name, addr in (("red", red_addr), ("yellow", yellow_addr), ("blue", blue_addr)):
        assert (addr >> 16) & 0xFFFF == hi, f"{name}: high half differs from red"
        assert addr & 0xFFFF < 0x8000, f"{name}: low half >= 0x8000 (sign extension)"

    stub  = ppc_lhz(7, 29, 0x0428)
    stub += ppc_lis(8, hi)
    stub += ppc_cmpwi(7, ONION_ID_RED)
    stub += ppc_bne(12)
    stub += ppc_addi(10, 8, red_addr & 0xFFFF)
    stub += ppc_b(base + 0x14, base + 0x2C)
    stub += ppc_cmpwi(7, ONION_ID_YELLOW)
    stub += ppc_bne(12)
    stub += ppc_addi(10, 8, yellow_addr & 0xFFFF)
    stub += ppc_b(base + 0x24, base + 0x2C)
    stub += ppc_addi(10, 8, blue_addr & 0xFFFF)
    stub += ppc_stw(29, 10, 0)
    stub += ppc_stw(0, 6, 0x042C)
    stub += ppc_b(base + 0x34, hook_addr + 4)

    assert len(stub) == 56, f"Stub size: {len(stub)}"
    return stub


# ---------------------------------------------------------------------------
# QOL: disable Pikmin tripping (feature "Disable Pikmin Trip")
#
# Tripping is triggered in ActCrowd::exec() (src/plugPikiKando/aiCrowd.cpp):
#
#     if (!hasBomb && mTravelDistance >= 100 && vel.length() > 110) {
#         if (getRand(1) >= 0.9999f && getRand(1) > 0.7f) {   // ~0.003% chance
#             mIsTripping = true;                              // -> anim PIKIANIM_Korobu
#             ...
#             return ACTOUT_Continue;
#         }
#         mTravelDistance = 0.0f;                              // "nothing happens"
#     }
#
# The FIRST conditional branch (bne, jumping to the mTravelDistance reset) is made
# unconditional: the trip block is then NEVER executed, and the odometer is always
# reset as in the "nothing happens" case.
#
# In PAL (GPIP01) the bne is at 0x800B6394: 40 82 00 d4  ->  48 00 00 d4
# (same target 0x800B6468, conditional opcode replaced by an unconditional b).
#
# The site is located by SIGNATURE rather than by hardcoded address, so the same
# code covers PAL and NTSC: the signature only uses version-independent machine
# words (float ops, fcmpo, cror, the mIsTripping = true writes), not the r2
# offsets or bl targets, which differ between versions. The bne's relative
# distance (0xD4) is identical in both versions since the function layout is the same.
# ---------------------------------------------------------------------------

# fsubs f3,f3,f4 ; fdivs f2,f3,f2 ; fmuls f1,f1,f2 ; fcmpo cr0,f1,f0 ; cror cr0eq,cr0gt,cr0eq
TRIP_SIG_PREFIX = bytes.fromhex("ec632028" "ec431024" "ec2100b2" "fc010040" "4c411382")
TRIP_BNE_OFF   = 0x14        # the bne to patch, right after the signature
TRIP_SETTRUE_OFF = 0x50      # li r0,1        (mIsTripping = true)
TRIP_STB_OFF     = 0x54      # stb r0,0x64(r31)
TRIP_SETTRUE_WORD = 0x38000001
TRIP_STB_WORD     = 0x981F0064


def find_trip_bne(f) -> list[tuple[int, int, int]]:
    """Locate the trip trigger's bne. Returns [(RAM address, ISO offset,
    original bne word)] for each matching site (normally exactly one)."""
    sites = []
    for file_off, ram_addr, size in dol_text_sections(f):
        f.seek(file_off)
        data = f.read(size)
        start = 0
        while True:
            i = data.find(TRIP_SIG_PREFIX, start)
            if i < 0:
                break
            start = i + 4

            def word(off: int):
                p = i + off
                if 0 <= p <= size - 4:
                    return struct.unpack(">I", data[p:p + 4])[0]
                return None

            bne = word(TRIP_BNE_OFF)
            if bne is None or (bne >> 16) != 0x4082:      # bne sur cr0
                continue
            if word(TRIP_SETTRUE_OFF) != TRIP_SETTRUE_WORD:  # li r0,1
                continue
            if word(TRIP_STB_OFF) != TRIP_STB_WORD:          # stb r0,0x64(r31)
                continue
            sites.append((ram_addr + i + TRIP_BNE_OFF,
                          file_off + i + TRIP_BNE_OFF, bne))
    return sites


def apply_trip_patch(f) -> tuple[bool, object]:
    """Apply the anti-trip patch. Best-effort: changes nothing unless the site is
    found uniquely (0 or >1 matches), so an ISO is never corrupted.
    Returns (applied, info)."""
    sites = find_trip_bne(f)
    if len(sites) != 1:
        return False, len(sites)
    ram, iso_off, bne = sites[0]
    new_word = 0x48000000 | (bne & 0x0000FFFC)  # bne target -> b target
    f.seek(iso_off)
    f.write(struct.pack(">I", new_word))
    return True, ram


# ---------------------------------------------------------------------------
# QOL: skip the ship part-collect cutscene.
#
# In PelletGoalState::init (pelletState.cpp), when a part reaches the ship, the
# game plays a single camera+text movie:
#     gameflow.mGameInterface->movie(DEMOID_CollectPart=79, ...);
# The virtual call (blrl) is replaced by a nop -> no camera and no text.
#
# Located by a version-independent signature (registers/immediates), unique in
# the DOL, around the call:
#     li r4,79 ; lwz r12,0(r3) ; li r5,0 ; li r9,-1 ; lwz r12,0xC(r12) ;
#     li r10,1 ; mtlr r12 ; blrl
# The last word of the signature IS the blrl (offset +0x1C), replaced by
# 0x60000000 (nop).
# ---------------------------------------------------------------------------
PART_COLLECT_SIG = bytes.fromhex(
    "3880004f" "81830000" "38a00000" "3920ffff" "818c000c" "39400001" "7d8803a6" "4e800021"
)
PART_COLLECT_BLRL_OFF  = 0x1C
PART_COLLECT_BLRL_WORD = 0x4E800021
PPC_NOP                = 0x60000000


def find_part_collect_blrl(f) -> list[tuple[int, int]]:
    """Locate the blrl of movie(DEMOID_CollectPart). Returns [(RAM address,
    ISO offset)] for each site (normally exactly one)."""
    sites = []
    sig_last = PART_COLLECT_SIG[-4:]
    for file_off, ram_addr, size in dol_text_sections(f):
        f.seek(file_off)
        data = f.read(size)
        start = 0
        while True:
            i = data.find(PART_COLLECT_SIG, start)
            if i < 0:
                break
            start = i + 4
            blrl_i = i + PART_COLLECT_BLRL_OFF
            if data[blrl_i:blrl_i + 4] != sig_last:  # must be the expected blrl
                continue
            sites.append((ram_addr + blrl_i, file_off + blrl_i))
    return sites


def apply_part_collect_patch(f) -> tuple[bool, object]:
    """Nop the blrl of the part-collect movie. Best-effort: changes nothing
    unless the site is found uniquely."""
    sites = find_part_collect_blrl(f)
    if len(sites) != 1:
        return False, len(sites)
    ram, iso_off = sites[0]
    f.seek(iso_off)
    f.write(struct.pack(">I", PPC_NOP))
    return True, ram


# ---------------------------------------------------------------------------
# QOL: skip the ship upgrade cutscene.
#
# Right after the collect movie, PelletGoalState::init calls
# playerState->preloadHenkaMovie(), which plays movie(DEMOID_ShipUpgrade*) when
# the ship levels up. That `bl` is at +0x24 from the start of the part-collect
# signature (0x8009A870 in PAL). It is nopped. preloadHenkaMovie ONLY plays
# this movie, so there are no side effects.
#
# IMPORTANT: this patch searches for the part-collect signature (whose last word
# is the blrl), so it must be applied BEFORE apply_part_collect_patch (which
# nops the blrl and would break the signature). The nop at +0x24 is outside the
# signature (0x24 > 0x20), so part-collect still finds the signature afterwards.
# ---------------------------------------------------------------------------
PART_COLLECT_HENKA_OFF = 0x24  # bl preloadHenkaMovie(), right after the blrl


def _find_part_collect_sites(f) -> list[tuple[int, int]]:
    """Return [(RAM address, ISO offset)] of the START of the part-collect signature."""
    sites = []
    for file_off, ram_addr, size in dol_text_sections(f):
        f.seek(file_off)
        data = f.read(size)
        start = 0
        while True:
            i = data.find(PART_COLLECT_SIG, start)
            if i < 0:
                break
            start = i + 4
            sites.append((ram_addr + i, file_off + i))
    return sites


def apply_ship_upgrade_patch(f) -> tuple[bool, object]:
    """Nop the call to preloadHenkaMovie() to skip the ship upgrade cutscene.
    Best-effort; checks that the target is really a bl."""
    sites = _find_part_collect_sites(f)
    if len(sites) != 1:
        return False, len(sites)
    sig_ram, sig_iso = sites[0]
    bl_iso = sig_iso + PART_COLLECT_HENKA_OFF
    f.seek(bl_iso)
    bl = struct.unpack(">I", f.read(4))[0]
    if (bl >> 26) != 18 or (bl & 1) != 1:  # must be a bl (opcode 18, link bit)
        return False, "not-bl"
    f.seek(bl_iso)
    f.write(struct.pack(">I", PPC_NOP))
    return True, sig_ram + PART_COLLECT_HENKA_OFF


class InvalidISOError(Exception):
    pass


def verify_iso(iso_path: str) -> None:
    """Verify the ISO, dispatching to the NTSC or PAL check by Game ID."""
    game_id = read_game_id(iso_path)
    if game_id[:3] in BASE_ID_BY_PATCHED_PREFIX:
        raise InvalidISOError(
            "This ISO is already patched. Please provide a clean Pikmin 1 ISO."
        )
    if game_id == NTSC_GAME_ID:
        return _verify_iso_ntsc(iso_path)
    if game_id != PAL_GAME_ID:
        raise InvalidISOError(
            f"Invalid Game ID: {game_id!r}.\n"
            f"Expected {PAL_GAME_ID.decode()} (PAL) or {NTSC_GAME_ID.decode()} (NTSC-U)."
        )
    return _verify_iso_pal(iso_path)


def _verify_iso_pal(iso_path: str) -> None:
    with open(iso_path, "rb") as f:
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


def _verify_iso_ntsc(iso_path: str) -> None:
    """Check that the NTSC hook site holds the expected instruction.

    The address was derived from the decomp, not observed on a console, so this
    check is essential. If the bytes do not match, patching is refused rather
    than producing a broken ISO.
    """
    with open(iso_path, "rb") as f:
        hook_off = ram_to_iso_offset(f, NTSC_HOOK_RAM_ADDR)
        f.seek(hook_off)
        hook_bytes = f.read(4)
        if hook_bytes != HOOK_EXPECTED:
            raise InvalidISOError(
                f"Unexpected bytes at NTSC hook location 0x{NTSC_HOOK_RAM_ADDR:08X} "
                f"(ISO offset 0x{hook_off:08x}): {hook_bytes.hex()}\n"
                f"Expected {HOOK_EXPECTED.hex()}. This NTSC-U ISO is not the expected one "
                "(different revision?)."
            )
        # Make sure a free area exists before writing anything.
        find_code_cave(f)


# --- Patched ISO identity ------------------------------------------------------
# The GameCube Game ID is EXACTLY 6 bytes (disc header 0x00-0x05), so the full run
# ID cannot fit. We keep the version prefix (P1P / P1E, read by the client) plus a
# 3-character [0-9A-Z] suffix derived from the WHOLE seed and the slot (46,656
# values, instead of the 1000 of seed[-3:]). The full run ID goes in the game name
# of the header (0x20, 0x3E0 bytes).
_ID_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DISC_NAME_OFF = 0x20
DISC_NAME_SIZE = 0x3E0


def make_game_id_suffix(seed: str, player: int) -> str:
    """Return a 3-character Game ID suffix specific to the seed AND the slot."""
    import hashlib
    n = int.from_bytes(hashlib.sha1(f"{seed}:{player}".encode("utf-8")).digest()[:8], "big")
    out = ""
    for _ in range(3):
        n, r = divmod(n, len(_ID_CHARS))
        out += _ID_CHARS[r]
    return out


def make_disc_title(seed: str, slot_name: str) -> str:
    """Return the game name written in the ISO header (visible in Dolphin)."""
    return f"Pikmin AP - Seed {seed} - {slot_name}"


def _write_disc_title(f, title: str) -> None:
    raw = title.encode("ascii", "replace")[:DISC_NAME_SIZE - 1]
    f.seek(DISC_NAME_OFF)
    f.write(raw + b"\x00" * (DISC_NAME_SIZE - len(raw)))


# --- Slot name in the ISO --------------------------------------------------------
# The client reads the slot name from game RAM to connect without asking. The
# disc header is not loaded into RAM, so a small block is written into a free
# (zero) area of the DOL .text, which is loaded.
# Format: SLOT_NAME_MAGIC + 1 length byte + UTF-8 name (<= SLOT_NAME_MAX).
SLOT_NAME_MAGIC = b"APPIKSLOT\x00"
SLOT_NAME_MAX = 64                     # 16 AP characters, up to 4 bytes each
SLOT_NAME_BLOCK = len(SLOT_NAME_MAGIC) + 1 + SLOT_NAME_MAX


def _write_slot_name(f, slot_name: str) -> bool:
    """Write the slot name block into a free DOL area. Returns True if written."""
    raw = slot_name.encode("utf-8")[:SLOT_NAME_MAX]
    if not raw:
        return False
    try:
        _ram, off = find_code_cave(f, SLOT_NAME_BLOCK + 8)
    except InvalidISOError:
        return False
    f.seek(off + 4)  # keep one zero word of margin after the preceding code
    f.write(SLOT_NAME_MAGIC + bytes([len(raw)]) + raw.ljust(SLOT_NAME_MAX, b"\x00"))
    return True


# --- Forced ship part animation ------------------------------------------------
# When the server validates a part location (release / !collect), the client makes
# the part visible on the S.S. Dolphin (UfoParts.mPartVisType), but its animation
# is never started, leaving the default pose. Since the client cannot call game
# functions, a "mailbox" is added:
#   block = PART_ANIM_MAGIC (8) + mailbox (u32, part fourCC) + stub
# The stub is called at the entry of PlayerState::renderParts() (every frame the
# ship is drawn): if mailbox != 0, it clears it and then calls
#   playerState->startUfoPartsMotion(mailbox, PelletMotion::After, false)
# exactly like startAfterMotions() at the start of the day.
PART_ANIM_MAGIC = b"APPIKMBX"
PART_ANIM_SITES = {
    # version: (renderParts, startUfoPartsMotion) -- decomp config/*/symbols.txt
    PAL_GAME_ID:  (0x800817CC, 0x800810C4),
    NTSC_GAME_ID: (0x80081914, 0x8008120C),
}
MFLR_R0 = 0x7C0802A6
PELLET_MOTION_AFTER = 2


def _ppc(v: int) -> bytes:
    return struct.pack(">I", v & 0xFFFFFFFF)


def build_part_anim_stub(block_ram: int, render_parts: int, start_motion: int) -> bytes:
    mb = block_ram + len(PART_ANIM_MAGIC)
    ha, lo = ((mb + 0x8000) >> 16) & 0xFFFF, mb & 0xFFFF
    code_ram = mb + 4
    ins = []
    lis   = lambda d, i: (15 << 26) | (d << 21) | (i & 0xFFFF)
    lwz   = lambda d, a, o: (32 << 26) | (d << 21) | (a << 16) | (o & 0xFFFF)
    stw   = lambda s_, a, o: (36 << 26) | (s_ << 21) | (a << 16) | (o & 0xFFFF)
    stwu  = lambda s_, a, o: (37 << 26) | (s_ << 21) | (a << 16) | (o & 0xFFFF)
    addi  = lambda d, a, i: (14 << 26) | (d << 21) | (a << 16) | (i & 0xFFFF)
    cmpwi = lambda a, i: (11 << 26) | (a << 16) | (i & 0xFFFF)
    beq   = lambda off: (16 << 26) | (12 << 21) | (2 << 16) | (off & 0xFFFC)
    mr    = lambda d, s_: (31 << 26) | (s_ << 21) | (d << 16) | (s_ << 11) | (444 << 1)
    b     = lambda fr, to, lk=0: (18 << 26) | ((to - fr) & 0x03FFFFFC) | lk
    ins += [lis(12, ha), lwz(11, 12, lo), cmpwi(11, 0), None,            # 0-3
            MFLR_R0, stwu(1, 1, -0x20), stw(0, 1, 0x24),                  # 4-6
            stw(3, 1, 0x8), stw(4, 1, 0xC), stw(5, 1, 0x10),              # 7-9
            addi(0, 0, 0), stw(0, 12, lo),                                # 10-11 mailbox = 0
            mr(4, 11), addi(5, 0, PELLET_MOTION_AFTER), addi(6, 0, 0),    # 12-14
            None,                                                         # 15 bl
            lwz(3, 1, 0x8), lwz(4, 1, 0xC), lwz(5, 1, 0x10),              # 16-18
            lwz(0, 1, 0x24), 0x7C0803A6, addi(1, 1, 0x20),                # 19-21 mtlr r0
            MFLR_R0, None]                                                # 22-23
    ins[3] = beq((22 - 3) * 4)
    ins[15] = b(code_ram + 15 * 4, start_motion, 1)
    ins[23] = b(code_ram + 23 * 4, render_parts + 4)
    return PART_ANIM_MAGIC + b"\x00" * 4 + b"".join(_ppc(i) for i in ins)


def apply_part_anim_patch(f, version: bytes) -> bool:
    """Install the mailbox and stub (PAL and NTSC)."""
    sites = PART_ANIM_SITES.get(version)
    if sites is None:
        return False
    render_parts, start_motion = sites
    try:
        hook_off = ram_to_iso_offset(f, render_parts)
        if _u32(f, hook_off) != MFLR_R0:
            return False  # ISO already modified at this spot
        size = len(build_part_anim_stub(0x80000000, render_parts, start_motion))
        ram, off = find_code_cave(f, size + 8)
    except InvalidISOError:
        return False
    block_ram, block_off = ram + 4, off + 4
    block = build_part_anim_stub(block_ram, render_parts, start_motion)
    f.seek(block_off)
    f.write(block)
    stub_ram = block_ram + len(PART_ANIM_MAGIC) + 4
    f.seek(hook_off)
    f.write(ppc_b(render_parts, stub_ram))
    return True


# --- Olimar's cause of death (DeathLink messages) -------------------------------
# The game does not remember what hurt Olimar. Navi::stimulate(Interaction&) is
# hooked -- every hit goes through it (attack, fire, bomb, crush, swallow...) --
# to record, in a small ring buffer, the interaction's vtable (= hit type) and
# its mOwner (= responsible creature).
#   block = DEATH_CAUSE_MAGIC (8) + index (u32) + 4 x (vtable u32, owner u32) + stub
DEATH_CAUSE_MAGIC = b"APPIKDTH"
DEATH_CAUSE_ENTRIES = 4
NAVI_STIMULATE_ADDR = {
    PAL_GAME_ID:  0x800FF820,   # stimulate__4NaviFR11Interaction
    NTSC_GAME_ID: 0x800FF968,
}


def build_death_cause_block(block_ram: int, stimulate: int) -> bytes:
    ring = block_ram + len(DEATH_CAUSE_MAGIC)          # index, then the entries
    ha, lo = ((ring + 0x8000) >> 16) & 0xFFFF, ring & 0xFFFF
    data_len = 4 + DEATH_CAUSE_ENTRIES * 8
    code_ram = ring + data_len
    lwz  = lambda d, a, o: (32 << 26) | (d << 21) | (a << 16) | (o & 0xFFFF)
    stw  = lambda s_, a, o: (36 << 26) | (s_ << 21) | (a << 16) | (o & 0xFFFF)
    addi = lambda d, a, i: (14 << 26) | (d << 21) | (a << 16) | (i & 0xFFFF)
    ins = [
        (15 << 26) | (12 << 21) | ha,                        # lis   r12, ring@ha
        addi(12, 12, lo),                                    # addi  r12, r12, ring@l
        lwz(11, 12, 0),                                      # lwz   r11, 0(r12)  index
        addi(11, 11, 1),                                     # addi  r11, r11, 1
        (28 << 26) | (11 << 21) | (11 << 16) | (DEATH_CAUSE_ENTRIES - 1),  # andi. r11, r11, 3
        stw(11, 12, 0),                                      # stw   r11, 0(r12)
        (21 << 26) | (11 << 21) | (11 << 16) | (3 << 11) | (0 << 6) | (28 << 1),  # slwi r11, r11, 3
        (31 << 26) | (12 << 21) | (12 << 16) | (11 << 11) | (266 << 1),           # add r12, r12, r11
        lwz(11, 4, 0), stw(11, 12, 4),                       # entry.vtable = interaction->vtbl
        lwz(11, 4, 4), stw(11, 12, 8),                       # entry.owner  = interaction->mOwner
        MFLR_R0,                                             # original instruction
        (18 << 26) | ((stimulate + 4 - (code_ram + 13 * 4)) & 0x03FFFFFC),  # b stimulate+4
    ]
    return DEATH_CAUSE_MAGIC + b"\x00" * data_len + b"".join(_ppc(i) for i in ins)


def apply_death_cause_patch(f, version: bytes) -> bool:
    """Install the "last hits received by Olimar" buffer (PAL and NTSC)."""
    stimulate = NAVI_STIMULATE_ADDR.get(version)
    if stimulate is None:
        return False
    try:
        hook_off = ram_to_iso_offset(f, stimulate)
        if _u32(f, hook_off) != MFLR_R0:
            return False  # ISO deja modifiee a cet endroit
        size = len(build_death_cause_block(0x80000000, stimulate))
        ram, off = find_code_cave(f, size + 8)
    except InvalidISOError:
        return False
    block_ram, block_off = ram + 4, off + 4
    block = build_death_cause_block(block_ram, stimulate)
    f.seek(block_off)
    f.write(block)
    code_ram = block_ram + len(DEATH_CAUSE_MAGIC) + 4 + DEATH_CAUSE_ENTRIES * 8
    f.seek(hook_off)
    f.write(ppc_b(stimulate, code_ram))
    return True


def patch_iso(iso_path: str, seed: str = "", disable_trip: bool = True,
              skip_part_collect: bool = True, skip_ship_upgrade: bool = True,
              suffix: str = "", title: str = "", slot_name: str = "") -> dict:
    """Patch the ISO, dispatching to the NTSC or PAL path by Game ID.

    `disable_trip`: QOL patch disabling Pikmin tripping (best-effort).
    `skip_part_collect`: QOL patch skipping the part-collect cutscene.
    `skip_ship_upgrade`: QOL patch skipping the ship upgrade cutscene.
    `suffix`: Game ID suffix (make_game_id_suffix); empty = seed[-3:] fallback
    (for .appik1 files generated by older versions).
    `title`: game name written in the header (full run ID).
    Returns a status dict (trip_patched / part_collect_patched / ship_upgrade_patched).
    """
    base_version = read_game_id(iso_path)
    if base_version == NTSC_GAME_ID:
        status = _patch_iso_ntsc(iso_path, seed, disable_trip, skip_part_collect, skip_ship_upgrade, suffix)
    else:
        status = _patch_iso_pal(iso_path, seed, disable_trip, skip_part_collect, skip_ship_upgrade, suffix)
    with open(iso_path, "r+b") as f:
        if title:
            _write_disc_title(f, title)
        # Slot name goes AFTER the other patches (the NTSC stub already occupies
        # its free area). The part anim / death cause blocks go BEFORE the slot
        # name so each block gets its own free area (the slot block contains zero
        # padding that could otherwise be mistaken for free space).
        status["part_anim_patched"] = apply_part_anim_patch(f, base_version)
        status["death_cause_patched"] = apply_death_cause_patch(f, base_version)
        if slot_name:
            status["slot_name_written"] = _write_slot_name(f, slot_name)
    return status


def _new_game_id(seed: str, prefix: bytes = PATCHED_GAME_ID_PREFIX, suffix: str = "") -> bytes:
    if not suffix:  # legacy format (compatibility)
        suffix = seed[-3:] if len(seed) >= 3 else seed.ljust(3, "0")
    return prefix + suffix.encode("ascii")


def _patch_iso_pal(iso_path: str, seed: str = "", disable_trip: bool = True,
                   skip_part_collect: bool = True, skip_ship_upgrade: bool = True,
                   suffix: str = "") -> dict:
    stub   = build_stub()
    branch = ppc_b(HOOK_RAM_ADDR, CAVE_RAM_ADDR)

    new_game_id = _new_game_id(seed, PATCHED_PREFIX_BY_VERSION[PAL_GAME_ID], suffix)

    status = {"trip_patched": False, "part_collect_patched": False, "ship_upgrade_patched": False}
    with open(iso_path, "r+b") as f:
        f.seek(CAVE_ISO_OFF)
        f.write(stub)
        f.seek(HOOK_ISO_OFF)
        f.write(branch)
        f.seek(0)
        f.write(new_game_id)
        if disable_trip:
            status["trip_patched"] = apply_trip_patch(f)[0]
        # ship-upgrade BEFORE part-collect (part-collect breaks the signature).
        if skip_ship_upgrade:
            status["ship_upgrade_patched"] = apply_ship_upgrade_patch(f)[0]
        if skip_part_collect:
            status["part_collect_patched"] = apply_part_collect_patch(f)[0]
    return status


# --- NTSC save file ------------------------------------------------------------
# In NTSC, MemoryCard::checkUseFile() recognizes the save file by NAME ONLY
# ("Pikmin dataFile"), without checking gameName/company (PAL does check them:
# memoryCard.cpp, #if VERSION_GPIP01). With a patched Game ID the game would
# adopt another game's save file (e.g. the vanilla GPIE one), and the CARD
# library would then refuse all writes (CARD_RESULT_NOPERM: different gamecode)
# without the game checking, so saving appears to succeed but nothing is written.
# The file is given a name specific to the patched ISO ("Pikmin " + Game ID) so
# it only matches its own saves. PAL is unchanged (existing saves stay compatible).
CARD_FILENAME_ORIG = b"Pikmin dataFile\x00"


def _dol_sections_all(f) -> list[tuple[int, int, int]]:
    """Return all DOL sections (7 .text + 11 .data) as (ISO offset, RAM, size)."""
    dol_off = _u32(f, 0x420)
    out = []
    for i in range(18):
        file_off = _u32(f, dol_off + 0x00 + i * 4)
        ram_addr = _u32(f, dol_off + 0x48 + i * 4)
        size     = _u32(f, dol_off + 0x90 + i * 4)
        if file_off and size:
            out.append((dol_off + file_off, ram_addr, size))
    return out


def apply_ntsc_card_filename_patch(f, game_id: bytes) -> bool:
    """Replace "Pikmin dataFile" with "Pikmin <GameID>" in the NTSC DOL."""
    new = b"Pikmin " + game_id[:6]
    assert len(new) < len(CARD_FILENAME_ORIG)
    new = new.ljust(len(CARD_FILENAME_ORIG), b"\x00")
    for file_off, _ram, size in _dol_sections_all(f):
        f.seek(file_off)
        data = f.read(size)
        idx = data.find(CARD_FILENAME_ORIG)
        if idx >= 0 and data.find(CARD_FILENAME_ORIG, idx + 1) < 0:
            f.seek(file_off + idx)
            f.write(new)
            return True
    return False


def _patch_iso_ntsc(iso_path: str, seed: str = "", disable_trip: bool = True,
                    skip_part_collect: bool = True, skip_ship_upgrade: bool = True,
                    suffix: str = "") -> dict:
    new_game_id = _new_game_id(seed, PATCHED_PREFIX_BY_VERSION[NTSC_GAME_ID], suffix)

    status = {"trip_patched": False, "part_collect_patched": False, "ship_upgrade_patched": False}
    with open(iso_path, "r+b") as f:
        hook_off = ram_to_iso_offset(f, NTSC_HOOK_RAM_ADDR)
        cave_ram, cave_off = find_code_cave(f)

        stub = build_stub(
            cave_addr=cave_ram,
            hook_addr=NTSC_HOOK_RAM_ADDR,
            red_addr=NTSC_FIXED_RED_BASE_ADDR,
            yellow_addr=NTSC_FIXED_YELLOW_BASE_ADDR,
            blue_addr=NTSC_FIXED_BLUE_BASE_ADDR,
        )
        branch = ppc_b(NTSC_HOOK_RAM_ADDR, cave_ram)

        f.seek(cave_off)
        f.write(stub)
        f.seek(hook_off)
        f.write(branch)
        f.seek(0)
        f.write(new_game_id)
        # Save file name specific to this ISO.
        status["card_filename_patched"] = apply_ntsc_card_filename_patch(f, new_game_id)
        if disable_trip:
            status["trip_patched"] = apply_trip_patch(f)[0]
        if skip_ship_upgrade:
            status["ship_upgrade_patched"] = apply_ship_upgrade_patch(f)[0]
        if skip_part_collect:
            status["part_collect_patched"] = apply_part_collect_patch(f)[0]
    return status


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