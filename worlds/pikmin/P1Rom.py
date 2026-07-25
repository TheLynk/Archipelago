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

# Prefixe du Game ID ecrit dans l'ISO patchee. Il sert aussi de marqueur de
# version : une fois patchee, l'ISO ne dit plus si elle vient du PAL ou du NTSC,
# et le client doit le savoir pour choisir les bonnes adresses memoire.
# Le PAL conserve "P1P" (compatibilite avec les ISO deja patchees).
PATCHED_PREFIX_BY_VERSION = {
    PAL_GAME_ID:  b"P1P",
    NTSC_GAME_ID: b"P1E",
}
# Prefixe patche -> Game ID d'origine, pour le client.
BASE_ID_BY_PATCHED_PREFIX = {v: k for k, v in PATCHED_PREFIX_BY_VERSION.items()}

VERSION_LABELS = {
    PAL_GAME_ID:  "PAL (Europe)",
    NTSC_GAME_ID: "NTSC-U (USA)",
}

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
# Tout ce qui precede reste strictement le chemin PAL, inchange et eprouve.
# Les valeurs ci-dessous viennent de la decomp projectPiki/pikmin :
#   - exitPiki__8GoalItem fait 0x27C octets dans les DEUX versions (code
#     identique), et le hook PAL tombe a +0x1E0 de son debut :
#         PAL  0x800EB1F4 + 0x1E0 = 0x800EB3D4
#         NTSC 0x800EB33C + 0x1E0 = 0x800EB51C
#   - la RAM de travail PAL est workString__3zen+0x2B0, un tampon .bss de 1 Ko ;
#     le meme symbole existe en NTSC a 0x803D1EE0, d'ou +0x2B0 = 0x803D2190.
# La zone de code (cave) n'est PAS codee en dur ici : contrairement au PAL,
# l'adresse PAL 0x8010CCE8 contient une vraie fonction en NTSC. Elle est donc
# cherchee dans le DOL au moment du patch (voir find_code_cave).
# ---------------------------------------------------------------------------

NTSC_HOOK_RAM_ADDR = 0x800EB51C

NTSC_FIXED_RED_BASE_ADDR    = 0x803D2190
NTSC_FIXED_YELLOW_BASE_ADDR = 0x803D2194
NTSC_FIXED_BLUE_BASE_ADDR   = 0x803D2198

# Taille du stub, et marge exigee quand on cherche une zone libre.
STUB_SIZE = 56
CAVE_MIN_SIZE = 60


def _u32(f, offset: int) -> int:
    f.seek(offset)
    return struct.unpack(">I", f.read(4))[0]


def read_game_id(iso_path: str) -> bytes:
    with open(iso_path, "rb") as f:
        return f.read(6)


def dol_text_sections(f) -> list[tuple[int, int, int]]:
    """Sections .text du DOL : [(offset fichier dans l'ISO, adresse RAM, taille)].

    L'emplacement du DOL est lu dans l'en-tete du disque (0x420) au lieu d'etre
    code en dur, ce qui rend la fonction independante de la version.
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
    """Convertit une adresse RAM en offset dans l'ISO, via l'en-tete du DOL."""
    for file_off, sec_ram, size in dol_text_sections(f):
        if sec_ram <= ram_addr < sec_ram + size:
            return file_off + (ram_addr - sec_ram)
    raise InvalidISOError(
        f"Adresse RAM 0x{ram_addr:08X} introuvable dans les sections .text du DOL."
    )


def find_code_cave(f, min_size: int = CAVE_MIN_SIZE) -> tuple[int, int]:
    """Cherche une suite d'octets nuls assez longue dans le .text du DOL.

    Renvoie (adresse RAM, offset ISO). L'adresse est purement interne au patch
    (le hook y saute et le stub en revient), le client n'en a pas besoin.
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
                    # aligne sur 4, deja garanti par le pas de boucle
                    return ram_addr + run_start, file_off + run_start
            else:
                run_start = None
    raise InvalidISOError(
        f"Aucune zone libre de {min_size} octets trouvee dans le DOL. "
        "Cette ISO est peut-etre deja modifiee."
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
    Hooks `stw r0, 0x042C(r6)` dans exitPiki__8GoalItem — retrait pikmin.
    Stores r29 per color, executes original stw, returns.

    Les valeurs par defaut sont celles du PAL : appele sans argument, cette
    fonction produit exactement le meme stub qu'avant l'ajout du NTSC.
    """
    base = cave_addr
    hi   = (red_addr >> 16) & 0xFFFF

    # Les trois emplacements sont adresses via un seul `lis` suivi de `addi`.
    # `addi` fait une extension de signe sur 16 bits : si la moitie basse
    # atteignait 0x8000, l'adresse calculee serait fausse de 0x10000.
    for name, addr in (("red", red_addr), ("yellow", yellow_addr), ("blue", blue_addr)):
        assert (addr >> 16) & 0xFFFF == hi, f"{name}: page haute differente de red"
        assert addr & 0xFFFF < 0x8000, f"{name}: moitie basse >= 0x8000 (extension de signe)"

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


class InvalidISOError(Exception):
    pass


def verify_iso(iso_path: str) -> None:
    """Verifie l'ISO. Aiguille vers le NTSC si besoin, sinon chemin PAL d'origine."""
    game_id = read_game_id(iso_path)
    if game_id.startswith(PATCHED_GAME_ID_PREFIX):
        raise InvalidISOError(
            "Cette ISO est deja patchee. Fournissez une ISO Pikmin 1 propre."
        )
    if game_id == NTSC_GAME_ID:
        return _verify_iso_ntsc(iso_path)
    if game_id != PAL_GAME_ID:
        raise InvalidISOError(
            f"Game ID invalide : {game_id!r}.\n"
            f"Attendu {PAL_GAME_ID.decode()} (PAL) ou {NTSC_GAME_ID.decode()} (NTSC-U)."
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
    """Verifie que le site de hook NTSC contient bien l'instruction attendue.

    L'adresse a ete derivee de la decomp, pas observee sur une console : cette
    verification est donc essentielle. Si les octets ne correspondent pas, on
    refuse de patcher plutot que de produire une ISO cassee.
    """
    with open(iso_path, "rb") as f:
        hook_off = ram_to_iso_offset(f, NTSC_HOOK_RAM_ADDR)
        f.seek(hook_off)
        hook_bytes = f.read(4)
        if hook_bytes != HOOK_EXPECTED:
            raise InvalidISOError(
                f"Octets inattendus au site de hook NTSC 0x{NTSC_HOOK_RAM_ADDR:08X} "
                f"(offset ISO 0x{hook_off:08x}) : {hook_bytes.hex()}\n"
                f"Attendu {HOOK_EXPECTED.hex()}. Cette ISO NTSC-U n'est pas celle prevue "
                "(revision differente ?)."
            )
        # Verifie qu'une zone libre existe avant de commencer a ecrire.
        find_code_cave(f)


def patch_iso(iso_path: str, seed: str = "") -> None:
    """Patche l'ISO. Aiguille vers le NTSC si besoin, sinon chemin PAL d'origine."""
    if read_game_id(iso_path) == NTSC_GAME_ID:
        return _patch_iso_ntsc(iso_path, seed)
    return _patch_iso_pal(iso_path, seed)


def _new_game_id(seed: str, prefix: bytes = PATCHED_GAME_ID_PREFIX) -> bytes:
    suffix = (seed[-3:] if len(seed) >= 3 else seed.ljust(3, "0")).encode("ascii")
    return prefix + suffix


def _patch_iso_pal(iso_path: str, seed: str = "") -> None:
    stub   = build_stub()
    branch = ppc_b(HOOK_RAM_ADDR, CAVE_RAM_ADDR)

    new_game_id = _new_game_id(seed, PATCHED_PREFIX_BY_VERSION[PAL_GAME_ID])

    with open(iso_path, "r+b") as f:
        f.seek(CAVE_ISO_OFF)
        f.write(stub)
        f.seek(HOOK_ISO_OFF)
        f.write(branch)
        f.seek(0)
        f.write(new_game_id)


def _patch_iso_ntsc(iso_path: str, seed: str = "") -> None:
    new_game_id = _new_game_id(seed, PATCHED_PREFIX_BY_VERSION[NTSC_GAME_ID])

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