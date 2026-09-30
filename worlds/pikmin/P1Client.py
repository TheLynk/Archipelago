import asyncio
import concurrent.futures
import json
import os
import random
import struct
import threading
import time
from typing import TYPE_CHECKING, Optional

import faulthandler
import logging

from . import P1Memory as dme

import Utils
from Utils import async_start
from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus

# Integrate Universal Tracker into the client ("Tracker" tab) if it is installed.
tracker_loaded = False
try:
    from worlds.tracker.TrackerClient import TrackerGameContext as SuperContext
    from worlds.tracker.TrackerClient import TrackerCommandProcessor as SuperCommandProcessor
    tracker_loaded = True
except ImportError:
    SuperContext = CommonContext
    SuperCommandProcessor = ClientCommandProcessor
from .P1Data import *
from .P1Symbols import (
    SYM_GAMEFLOW,
    SYM_PIKMIN_ADDRESSES,
    SYM_ONION_DYN_ADDRS,
    SYM_ALLPIKIS_ADDRS,
    SYM_ONION_STAGE_ADDRS,
    SYM_ITEM_MGR_PTR,
    SYM_PLAYER_STATE_PTR,
    PLAYERSTATE_OFFSETS,
    SYM_GSYS_PTR,
    STDSYSTEM_LANGUAGE_OFFSET,
    LANGUAGE_IDS,
    UFO_PART_ORDER,
    SYM_TUTORIAL_WINDOW_PTR,
    TUTORIAL_TEXT_CHAIN,
    TUT_PART_TEXT_RANGES,
    SKIP_EVENT_DEMOFLAGS,
    SYM_TRIP_RAND_CONST,
    TRIP_DISABLED_FLOAT,
    TRIP_NORMAL_FLOAT,
    TRIP_FORCED_FLOAT,
    CONTAINER_COLOR_BIT,
    CONTAINER_BOOT_ALL,
    SECTION_ONE_PLAYER,
    ONEPLAYER_NEW_PIKI_GAME,
    ONEPLAYER_MAP_SELECT,
    ONEPLAYER_CARD_SELECT,
    ONION_CHAIN,
    OBJTYPE_GOAL,
    OBJTYPE_PELLET,
    PELLET_CHAIN,
    SYM_PELLET_MGR_PTR,
    ENTRYSTATUS_KILL,
    SYM_RADAR_INFO_PTR,
    RADAR_CHAIN,
    SYM_DEAD_PIKIS,
    SYM_BORN_PIKIS,
    SYM_ORIMA_DEAD,
    SYM_NAVI_MGR_PTR,
    NAVI_CHAIN,
    NAVISTATE_PRESSED,
    NAVISTATE_WALK,
    SYM_ROUTE_MGR_PTR,
    ROUTE_CHAIN,
    WP_FLAG_INWATER,
    SYM_MAP_WINDOW_PTR,
    MAP_GAME2SCR,
    WORLDMAP_CHAIN,
    DWM_MODE_OPERATION,
    CPM_MODE_APPEAR,
    CP_APPEAR_START,
)
from .P1Rom import BASE_ID_BY_PATCHED_PREFIX

if TYPE_CHECKING:
    import kvui

SCOUT_RETRY_INTERVAL = 5.0  # seconds between scout retries


def _gf(field: str) -> MemoryAddress:
    """Address of a `gameflow` field, per game version (source: decomp)."""
    return {g: t[field] for g, t in SYM_GAMEFLOW.items()}


# Derived from the decomp: gameflow+0x1CB / +0x2F8 / +0x2FF.
UNLOCKED_AREAS: MemoryAddress = _gf("UNLOCKED_AREAS")
TIME_HOURS: MemoryAddress = _gf("TIME_HOURS")   # int, 7=morning, >=19=end of day
DAY_NUMBER: MemoryAddress = _gf("DAY_NUMBER")   # byte, current day
# Heap (dynamically allocated): no static symbol, addresses found manually.
COUNT_TOTAL_PARTS: MemoryAddress = mem(0x812427FF, 0x81249DE7)  # byte
COUNT_REQUIRED_PARTS: MemoryAddress = mem(0x81242803, 0x81249DEB)  # byte

# Ship part hint text address (PAL) — universal for all parts
# Hardcoded PAL address, kept only as a reference value in /debugtext.
# Reads/writes resolve the address via resolve_ship_part_text_addr().
SHIP_PART_TEXT_ADDR = 0x807B100A
SHIP_PART_TEXT_LENGTH = 313  # 0x807B1143 - 0x807B100A
LANG_NAMES = {"en": "English", "fr": "Français", "de": "Deutsch", "it": "Italiano", "es": "Español"}

LANG_MSG_DETECTED = {
    "en": "Language detected",
    "fr": "Langue détectée",
    "de": "Sprache erkannt",
    "it": "Lingua rilevata",
    "es": "Idioma detectado",
}

# Active options announced on connection, per game language.
BOND_ACTIVE_MSG = {
    "en": "Olimar-Pikmin Bond active (-{dmg} HP per Pikmin death).",
    "fr": "Lien Olimar/Pikmin actif (-{dmg} PV par Pikmin mort).",
    "de": "Olimar-Pikmin-Band aktiv (-{dmg} LP pro gestorbenem Pikmin).",
    "it": "Legame Olimar-Pikmin attivo (-{dmg} PV per ogni Pikmin morto).",
    "es": "Vínculo Olimar-Pikmin activo (-{dmg} PS por cada Pikmin muerto).",
}
DEATHLINK_ACTIVE_MSG = {
    "en": "DeathLink active (mode {mode}).",
    "fr": "DeathLink actif (mode {mode}).",
    "de": "DeathLink aktiv (Modus {mode}).",
    "it": "DeathLink attivo (modalità {mode}).",
    "es": "DeathLink activo (modo {mode}).",
}
TRAPLINK_ACTIVE_MSG = {
    "en": "TrapLink active.",
    "fr": "TrapLink actif.",
    "de": "TrapLink aktiv.",
    "it": "TrapLink attivo.",
    "es": "TrapLink activo.",
}

# Connection is deferred until the game is detected.
WAIT_GAME_MSG = {
    "en": "Waiting for Pikmin (patched ISO) to be running in Dolphin before connecting...",
    "fr": "En attente de Pikmin (ISO patchée) dans Dolphin avant la connexion...",
    "de": "Warte darauf, dass Pikmin (gepatchte ISO) in Dolphin läuft, bevor verbunden wird...",
    "it": "In attesa che Pikmin (ISO patchata) sia avviato in Dolphin prima della connessione...",
    "es": "Esperando a que Pikmin (ISO parcheada) se ejecute en Dolphin antes de conectar...",
}
SLOT_FROM_ISO_MSG = {
    "en": "Slot name read from the patched ISO: {name}",
    "fr": "Nom du slot lu dans l'ISO patchée : {name}",
    "de": "Slot-Name aus der gepatchten ISO gelesen: {name}",
    "it": "Nome dello slot letto dall'ISO patchata: {name}",
    "es": "Nombre del slot leído de la ISO parcheada: {name}",
}

SYNC_ACTIVE_MSG = {
    "en": "Save loaded — AP sync active.",
    "fr": "Sauvegarde chargée — synchronisation AP active.",
    "de": "Spielstand geladen — AP-Synchronisierung aktiv.",
    "it": "Salvataggio caricato — sincronizzazione AP attiva.",
    "es": "Partida cargada — sincronización AP activa.",
}

SYNC_PAUSED_MSG = {
    "en": "Returned to menu — AP sync paused.",
    "fr": "Retour au menu — synchronisation AP en pause.",
    "de": "Zurück zum Menü — AP-Synchronisierung pausiert.",
    "it": "Ritorno al menu — sincronizzazione AP in pausa.",
    "es": "Vuelta al menú — sincronización AP en pausa.",
}

DEATHLINK_RECEIVED_MSG = {
    "en": "DeathLink received — Olimar has been eliminated.",
    "fr": "DeathLink reçu — Olimar est éliminé.",
    "de": "DeathLink erhalten — Olimar wurde ausgeschaltet.",
    "it": "DeathLink ricevuto — Olimar è stato eliminato.",
    "es": "DeathLink recibido — Olimar ha sido eliminado.",
}

def _read_apworld_version() -> str:
    """Apworld version, read from the archipelago.json manifest.

    Works from source (folder) and from a .apworld (zip): tries importlib.resources
    first (zip-aware), then falls back to plain file access.
    """
    try:
        from importlib.resources import files
        data = (files(__package__) / "archipelago.json").read_text(encoding="utf-8")
        return json.loads(data).get("version", "unknown")
    except Exception:
        pass
    try:
        path = os.path.join(os.path.dirname(__file__), "archipelago.json")
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("version", "unknown")
    except Exception:
        return "unknown"


APWORLD_VERSION = _read_apworld_version()

# Item id -> readable name (Pikmin bonuses), for debug logs.
ITEM_ID_TO_NAME: dict[int, str] = {ap_id: name for name, ap_id in FILLER_ITEMS.items()}


def _named_counts(applied: dict) -> dict:
    """Replace item ids with readable names in an {id: n} dict.

    Sorted by item name for stable output; unknown ids fall back to the raw id.
    """
    out = {}
    for item_id, n in applied.items():
        name = ITEM_ID_TO_NAME.get(item_id, f"#{item_id}")
        out[name] = n
    return dict(sorted(out.items()))

# Language detection.
#
# Read `gsys->mLanguageID` (StdSystem, include/system.h of the projectPiki/pikmin
# decomp). `gsys` is a global pointer and mLanguageID is at offset 0x1A0. Valid at
# any point in the game.
#
# NTSC-U: the field does not exist (English-only game) and 0x1A0 holds the vtable
# pointer, so it is never read and "en" is returned.

MEMORY_OVERRIDE_OPTION = '"Enable Emulated Memory Size Override"'

# Plausible bounds for a MEM1 pointer (guards against wild reads).
_RAM_MIN = 0x80000000
_RAM_MAX = 0x81800000


def resolve_ship_part_text_addr(game: Game) -> Optional[int]:
    """Address of the currently displayed text buffer, or None.

    Follows the pointer chain from the decomp:
        tutorialWindow (statique) -> ogScrTutorialMgr
          +0x00  mMessageMgr      -> ogScrMessageMgr
          +0x4F2 mFormattedDisplayStrings[0]

    Depends only on static symbols and struct offsets, so it works on both
    PAL and NTSC-U.
    """
    mgr = resolve_message_mgr(game)
    if mgr is None:
        return None
    return mgr + TUTORIAL_TEXT_CHAIN["MSGMGR_FORMATTED"]


def resolve_message_mgr(game: Game) -> Optional[int]:
    """Address of the current ogScrMessageMgr, or None if no text window is open."""
    tw_addr = SYM_TUTORIAL_WINDOW_PTR.get(game)
    if tw_addr is None:
        return None
    try:
        tut = struct.unpack(">I", dme.read_bytes(tw_addr, 4))[0]
        if not (_RAM_MIN <= tut < _RAM_MAX):
            return None  # no active text window
        mgr = struct.unpack(
            ">I", dme.read_bytes(tut + TUTORIAL_TEXT_CHAIN["TUTORIALMGR_MESSAGEMGR"], 4)
        )[0]
        if not (_RAM_MIN <= mgr < _RAM_MAX):
            return None
    except Exception:
        return None
    return mgr


# EnumTutorial ranges that may be replaced by a hint.
# The hint is shown only BEFORE collection:
#   - "discovery": approaching a part for the first time
#   - "info"     : interacting with a part not yet collected
# Excluded:
#   - "collect": the part pickup text (a location hint is meaningless once the
#     part is obtained).
#   - "power"  : ship upgrade text, unrelated to a location.
HINTABLE_TEXT_KINDS = ("discovery", "info")


def read_displayed_message_id(msgmgr: int) -> Optional[int]:
    """EnumTutorial id of the currently displayed text, or None."""
    try:
        page = struct.unpack(
            ">h", dme.read_bytes(msgmgr + TUTORIAL_TEXT_CHAIN["MSGMGR_CURR_PAGE"], 2)
        )[0]
        if not (0 <= page < 300):  # mPageInfos[300]
            return None
        info_ptr = struct.unpack(
            ">I",
            dme.read_bytes(
                msgmgr + TUTORIAL_TEXT_CHAIN["MSGMGR_PAGE_INFOS"] + page * 4, 4
            ),
        )[0]
        if not (_RAM_MIN <= info_ptr < _RAM_MAX):
            return None
        return struct.unpack(
            ">h",
            dme.read_bytes(info_ptr + TUTORIAL_TEXT_CHAIN["TEXTINFO_MSG_UNIQUE_ID"], 2),
        )[0]
    except Exception:
        return None


def part_from_message_id(msg_id: int) -> Optional[str]:
    """Name of the part matching a text ID, or None if it is not a part text.

    Part texts occupy specific EnumTutorial ranges, each covering the 30 parts in
    UfoPartIndex order. Any other ID is a tutorial or story text and must be left
    untouched.
    """
    for kind in HINTABLE_TEXT_KINDS:
        base = TUT_PART_TEXT_RANGES[kind]
        if base <= msg_id < base + len(UFO_PART_ORDER):
            return UFO_PART_ORDER[msg_id - base]
    return None


def read_displayed_part(game: Game) -> Optional[str]:
    """Name of the part whose text is displayed, or None if it is not a part text.

    The text is identified by its message ID (TextInfoType.mMsgUniqueId), not by
    `gameflow.mShipTextPartID`, which is persistent: it keeps the last part even
    during an unrelated text.
    """
    msgmgr = resolve_message_mgr(game)
    if msgmgr is None:
        return None
    msg_id = read_displayed_message_id(msgmgr)
    if msg_id is None:
        return None
    return part_from_message_id(msg_id)


def _oneplayer_subsection(game: Game) -> Optional[int]:
    """Current OnePlayer subsection (OnePlayerSectionID enum), or None.

    Reads `gameflow.mNextOnePlayerSectionID`. Values:
      - ONEPLAYER_NewPikiGame (7): Olimar in a level, day in progress;
      - ONEPLAYER_MapSelect (6)  : world map / level select;
      - ONEPLAYER_CardSelect (1) : save selection menu.
    Returns None outside story mode (title screen, boot).

    `mCurrGameSectionID` (outer section) is not enough: all these menus are
    subsections of SECTION_OnePlayer. `DAY_NUMBER` is not either: it keeps a
    non-zero residual value on these menus.
    """
    gf = SYM_GAMEFLOW.get(game)
    if not gf:
        return None
    try:
        section = struct.unpack(">i", dme.read_bytes(gf["GAME_SECTION"], 4))[0]
        if section != SECTION_ONE_PLAYER:
            return None
        return struct.unpack(">i", dme.read_bytes(gf["ONEPLAYER_SECTION"], 4))[0]
    except Exception:
        return None


def is_day_active(game: Game) -> bool:
    """True if the day has actually started (interactive gameplay).

    Reads `gameflow.mIsPauseAllowed`: TRUE only while the player controls Olimar,
    FALSE during loading, the day intro cutscene and the end of day. Used to hold
    traps until the day has really started.
    """
    gf = SYM_GAMEFLOW.get(game)
    if not gf:
        return False
    try:
        return struct.unpack(">i", dme.read_bytes(gf["PAUSE_ALLOWED"], 4))[0] != 0
    except Exception:
        return False


def is_overlay_active(game: Game) -> bool:
    """True if a screen covers the gameplay (traps must be suspended).

    Per the decomp (newPikiGame.cpp, GameFlow):
      - mIsUIOverlayActive (_338): Pause menu (Start), map/controls (Y),
        ship part text, other windows over the game;
      - mPauseAll (_33C): gameplay frozen (onion menu, cutscene);
      - mIsTutorialTextActive (_340): text window open.
    On read failure the overlay is assumed active (safer to delay a trap than to
    apply it while a menu is open).
    """
    gf = SYM_GAMEFLOW.get(game)
    if not gf:
        return True
    try:
        for key in ("UI_OVERLAY_ACTIVE", "PAUSE_ALL", "TUTORIAL_TEXT_ACTIVE"):
            if struct.unpack(">i", dme.read_bytes(gf[key], 4))[0] != 0:
                return True
        return False
    except Exception:
        return True


def is_in_level(game: Game) -> bool:
    """True if the player controls Olimar in a level (day in progress).

    Guards handlers that READ level-specific memory: part collection (heap
    objects) and squad Pikmin counters. Outside a level these addresses are not
    meaningful and could send false checks.
    """
    return _oneplayer_subsection(game) == ONEPLAYER_NEW_PIKI_GAME


def is_save_active(game: Game) -> bool:
    """True if a save is in progress: in a level OR on the world map.

    Broader guard than is_in_level, for item RECEPTION (Pikmin bonuses persist via
    STAGE and apply on the next level) and area unlocking (which must be visible
    on the world map). Excludes the save selection menu (CardSelect) and the title
    screen.

    Also the reference for the sync status message, so passing through the world
    map between levels does not report sync as paused.
    """
    return _oneplayer_subsection(game) in (ONEPLAYER_NEW_PIKI_GAME, ONEPLAYER_MAP_SELECT)


def read_orima_dead(game: Game) -> bool:
    """True if Olimar is dead (GameStat::orimaDead, set to 1 by NaviDeadState)."""
    addr = SYM_ORIMA_DEAD.get(game)
    if addr is None:
        return False
    try:
        return dme.read_byte(addr) != 0
    except Exception:
        return False


def read_dead_pikis_total(game: Game) -> Optional[int]:
    """Total dead Pikmin (GameStat::deadPikis, sum of Blue+Red+Yellow), or None."""
    addr = SYM_DEAD_PIKIS.get(game)
    if addr is None:
        return None
    try:
        blue, red, yellow = struct.unpack(">iii", dme.read_bytes(addr, 12))
    except Exception:
        return None
    return blue + red + yellow


def _resolve_olimar(game: Game) -> Optional[int]:
    """Address of Olimar's Navi object, or None.

    naviMgr -> +MONO_OBJECTLIST (Creature**) -> [0] = Navi (Olimar in single player).
    """
    mgr_ptr = SYM_NAVI_MGR_PTR.get(game)
    if mgr_ptr is None:
        return None
    try:
        mgr = struct.unpack(">I", dme.read_bytes(mgr_ptr, 4))[0]
        if not (_RAM_MIN <= mgr < _RAM_MAX):
            return None
        obj_list = struct.unpack(">I", dme.read_bytes(mgr + NAVI_CHAIN["MONO_OBJECTLIST"], 4))[0]
        if not (_RAM_MIN <= obj_list < _RAM_MAX):
            return None
        navi = struct.unpack(">I", dme.read_bytes(obj_list, 4))[0]
        if not (_RAM_MIN <= navi < _RAM_MAX):
            return None
        return navi
    except Exception:
        return None


def kill_olimar(game: Game) -> bool:
    """Kill Olimar when a DeathLink is received.

    Writing mHealth = 0 is not enough: the game only checks health inside damage
    states, not continuously. Olimar is therefore forced into the "pressed" state
    (NaviPressedState) with an already-expired timer; its exec(), called every
    frame, then sees mHealth <= 1 and performs the real transition to
    NaviDeadState itself (full sequence: death animation, end of day). The game
    runs the transition, we only prime it.

    Steps:
      1. Resolve Olimar (Navi).
      2. Find the NaviPressedState instance via the StateMachine tables.
      3. Write mCurrState = NaviPressedState, mPressedTimer < 0, mHealth = 0.

    If a read fails, falls back to writing mHealth only.
    Returns True if the kill was primed.
    """
    navi = _resolve_olimar(game)
    if navi is None:
        return False

    C = NAVI_CHAIN

    def u32(addr: int) -> Optional[int]:
        try:
            v = struct.unpack(">I", dme.read_bytes(addr, 4))[0]
        except Exception:
            return None
        return v if _RAM_MIN <= v < _RAM_MAX else None

    # Only prime the kill when Olimar is in his normal controllable state
    # (NaviWalkState). In demo/cutscene states the forced state gets overwritten
    # by the game, leaving only mHealth = 0 (a zombie Olimar). Retry next tick.
    walk = _resolve_state_instance(navi, NAVISTATE_WALK)
    cur = u32(navi + C["NAVI_CURRSTATE"])
    if walk is None or cur != walk:
        return False

    try:
        # Always set health to 0.
        dme.write_bytes(navi + C["CREATURE_HEALTH"], struct.pack(">f", 0.0))

        sm = u32(navi + C["NAVI_STATEMACHINE"])
        if sm is None:
            return True  # health 0 written, but no state to force
        state_indexes = u32(sm + C["SM_STATEINDEXES"])
        states = u32(sm + C["SM_STATES"])
        if state_indexes is None or states is None:
            return True
        # mStateIndexes[NAVISTATE_Pressed] -> index into mStates
        idx = struct.unpack(">i", dme.read_bytes(state_indexes + NAVISTATE_PRESSED * 4, 4))[0]
        if idx < 0 or idx > 64:
            return True
        pressed_state = u32(states + idx * 4)
        if pressed_state is None:
            return True

        # Prime: expired timer + Pressed state; the game's exec() performs the death.
        dme.write_bytes(navi + C["NAVI_PRESSED_TIMER"], struct.pack(">f", -1.0))
        dme.write_bytes(navi + C["NAVI_CURRSTATE"], struct.pack(">I", pressed_state))
        return True
    except Exception:
        return False


# --- Traps ---------------------------------------------------------------

# Trap effect settings.
TIME_TRAP_HOURS = 2      # game hours added to the clock
DAMAGE_TRAP_LOSS = 20.0  # default % of health removed (option damage_trap_amount)
DAMAGE_TRAP_FLOOR = 2.0  # floor so Olimar is not killed (death at <= 1.0)
TELEPORT_TRAP_LIFT = 60.0    # height added so Olimar drops onto the terrain


def apply_time_trap(game: Game) -> bool:
    """Advance the clock, reducing the time left in the day.

    Writes mCurrentGameHour (integer hour, TIME_HOURS), not mTimeOfDay:
    WorldClock::update recomputes mTimeOfDay every frame from mCurrentGameHour.
    """
    gf = SYM_GAMEFLOW.get(game)
    if not gf:
        return False
    addr = gf["TIME_HOURS"]
    try:
        h = struct.unpack(">i", dme.read_bytes(addr, 4))[0]
        # Cap at the end-of-day hour (19h): beyond it the game would record the
        # graph point out of bounds (TimeGraph::set is unchecked).
        graph = _read_population_graph(game)
        end = graph[2] if graph else 19
        new = min(h + TIME_TRAP_HOURS, end)
        if new > h:
            dme.write_bytes(addr, struct.pack(">i", new))
        _fill_population_graph_gaps(game)
        return True
    except Exception:
        return False


# --- Population graph and Time Trap --------------------------------------------
# PlayerState::mPerHourGraph (TimeGraph @ PlayerState+0x18C): u16 mStartTime,
# u16 mEndTime, PikiNum* mEntries (int[3] Blue/Red/Yellow per hour, -1 = empty).
# The game only records a point when the hour CHANGES; a Time Trap skips hours,
# which stay at -1, and the drawing stops at the first -1 (ogGraph). Skipped
# hours are filled with the previous hour's value (flat curve).

def _read_population_graph(game: Game) -> Optional[tuple]:
    """Return (entries address, start hour, end hour), or None."""
    ps_ptr = SYM_PLAYER_STATE_PTR.get(game)
    if ps_ptr is None:
        return None
    ps = struct.unpack(">I", dme.read_bytes(ps_ptr, 4))[0]
    if not (_RAM_MIN <= ps < _RAM_MAX):
        return None
    g = ps + PLAYERSTATE_OFFSETS["mPerHourGraph"]
    start, end = struct.unpack(">HH", dme.read_bytes(g, 4))
    entries = struct.unpack(">I", dme.read_bytes(g + 4, 4))[0]
    if not (_RAM_MIN <= entries < _RAM_MAX) or not (0 <= start <= end <= 24):
        return None
    return entries, start, end


def _fill_population_graph_gaps(game: Game) -> None:
    """Fill skipped hours (-1) up to the current hour."""
    gf = SYM_GAMEFLOW.get(game)
    if not gf:
        return
    try:
        graph = _read_population_graph(game)
        if not graph:
            return
        entries, start, end = graph
        hour = struct.unpack(">i", dme.read_bytes(gf["TIME_HOURS"], 4))[0]
        upto = min(hour, end)
        if upto < start:
            return
        n = upto - start + 1
        vals = list(struct.unpack(f">{n * 3}i", dme.read_bytes(entries, n * 12)))
        allp = GAMESTAT_ALLPIKIS_ADDRS.get(game, {})
        current = {idx: struct.unpack(">i", dme.read_bytes(allp[c], 4))[0]
                   for c, idx in _BORN_COLOR_INDEX.items() if c in allp}
        changed = False
        for idx in range(3):
            last = None
            for i in range(n):
                k = i * 3 + idx
                if vals[k] >= 0:
                    last = vals[k]
                    continue
                fill = last if last is not None else current.get(idx)
                if fill is None or fill < 0:
                    continue
                vals[k] = fill
                last = fill
                changed = True
        if changed:
            dme.write_bytes(entries, struct.pack(f">{n * 3}i", *vals))
    except Exception as e:
        logger.debug(f"population graph fill: {e}")


async def handle_population_graph(ctx: "P1Context", game: Game) -> None:
    """Fill population graph gaps (Time Trap, TrapLink...) every tick."""
    _fill_population_graph_gaps(game)


def apply_end_day_trap(game: Game) -> bool:
    """Force the end of the day by writing gameflow.mIsDayEndTriggered.

    The end-of-day sequence (OnePlayerSection) consumes this flag outside menus
    and starts the end-of-day cutscene via gameflow.mGameInterface. Arming the
    flag at the wrong time makes the consumer dereference a null pointer at
    offset +0xEC (crash "Invalid read from 0x000000ec"). Dangerous cases:
      - end of day already active or pending (sunset, Olimar's death, or an
        earlier End Day Trap not yet consumed);
      - mGameInterface is null (section transition in progress).
    The flag is therefore only armed in a stable state; otherwise False is
    returned and the trap stays pending.

    Offsets derived from include/gameflow.h around mCurrGameSectionID (_1EC):
      _1E4 s16 mIsDayEndActive           = DAY_END_TRIGGERED - 2
      _1E6 s16 mIsDayEndTriggered        = DAY_END_TRIGGERED
      _1E8 GameInterface* mGameInterface = GAME_SECTION - 4
    """
    gf = SYM_GAMEFLOW.get(game)
    if not gf:
        return False
    day_end_active = gf["DAY_END_TRIGGERED"] - 2
    game_interface_ptr = gf["GAME_SECTION"] - 4
    try:
        # End of day already active or armed: do not re-trigger.
        if struct.unpack(">h", dme.read_bytes(day_end_active, 2))[0] != 0:
            return False
        if struct.unpack(">h", dme.read_bytes(gf["DAY_END_TRIGGERED"], 2))[0] != 0:
            return False
        # mGameInterface must point to a valid object: the end-of-day cutscene
        # dereferences it (source of the +0xEC crash).
        gi = struct.unpack(">I", dme.read_bytes(game_interface_ptr, 4))[0]
        if not (_RAM_MIN <= gi < _RAM_MAX):
            return False
        dme.write_bytes(gf["DAY_END_TRIGGERED"], struct.pack(">h", 1))
        return True
    except Exception:
        return False


DAMAGE_TRAP_MAX_HEALTH = 100.0  # Olimar's max health


def apply_damage_trap(game: Game, ctx=None) -> bool:
    """Hurt Olimar by `damage_trap_amount` % of his max health.

    Option `damage_trap_can_kill`: if health drops to the game's death threshold
    (<= 1.0), Olimar dies (real death sequence via kill_olimar, which also
    triggers the classic DeathLink); otherwise DAMAGE_TRAP_FLOOR health is left.
    """
    navi = _resolve_olimar(game)
    if navi is None:
        return False
    slot_data = (getattr(ctx, "slot_data", None) or {}) if ctx is not None else {}
    amount = float(slot_data.get("damage_trap_amount", DAMAGE_TRAP_LOSS))
    can_kill = bool(slot_data.get("damage_trap_can_kill", 0))
    loss = DAMAGE_TRAP_MAX_HEALTH * amount / 100.0
    addr = navi + NAVI_CHAIN["CREATURE_HEALTH"]
    try:
        h = struct.unpack(">f", dme.read_bytes(addr, 4))[0]
        new = h - loss
        if new <= 1.0:
            if can_kill:
                # kill_olimar() only acts if Olimar is controllable; otherwise
                # return False so the trap stays pending and retries next tick.
                if not kill_olimar(game):
                    return False
                if ctx is not None:
                    ctx._client_kill_reason = "Damage Trap"
                return True
            new = DAMAGE_TRAP_FLOOR
        # Never heal: if Olimar is already lower, leave as is.
        if new < h:
            dme.write_bytes(addr, struct.pack(">f", new))
        return True
    except Exception:
        return False


WP_FLAG_PEBBLE = 0x02         # WayPointFlags::Pebble (obstacle)
WP_LINKS_OFF = 0x14           # int mLinkIndices[8]
WP_LINKCOUNT_OFF = 0x34       # int mLinkCount


def _read_waypoint_graph(game: Game) -> Optional[list]:
    """Read the whole waypoint network (group 0) in one read.

    Returns a list of dicts {pos, open, flags, links}, or None.
    """
    mgr_ptr = SYM_ROUTE_MGR_PTR.get(game)
    if mgr_ptr is None:
        return None
    R = ROUTE_CHAIN

    def u32(addr: int) -> Optional[int]:
        try:
            v = struct.unpack(">I", dme.read_bytes(addr, 4))[0]
        except Exception:
            return None
        return v if _RAM_MIN <= v < _RAM_MAX else None

    route_mgr = u32(mgr_ptr)
    if route_mgr is None:
        return None
    group = u32(route_mgr + R["ROUTEMGR_GROUPLIST"])
    if group is None:
        return None
    waypoints = u32(group + R["GROUP_WAYPOINTS"])
    if waypoints is None:
        return None
    try:
        count = struct.unpack(">i", dme.read_bytes(group + R["GROUP_NUMPOINTS"], 4))[0]
    except Exception:
        return None
    if not (0 < count <= 4000):
        return None
    size = R["WAYPOINT_SIZE"]
    try:
        raw = dme.read_bytes(waypoints, count * size)
    except Exception:
        return None
    graph = []
    for i in range(count):
        o = i * size
        x, y, z = struct.unpack_from(">fff", raw, o + R["WP_POSITION"])
        n = struct.unpack_from(">i", raw, o + WP_LINKCOUNT_OFF)[0]
        links = [l for l in struct.unpack_from(">8i", raw, o + WP_LINKS_OFF)[:max(0, min(n, 8))]
                 if 0 <= l < count]
        graph.append({"pos": (x, y, z), "open": raw[o + R["WP_ISOPEN"]] != 0,
                      "flags": raw[o + R["WP_FLAGS"]], "links": links})
    return graph


def _safe_teleport_position(game: Game, origin: tuple) -> Optional[tuple]:
    """Pick a safe destination for the Teleport Trap.

    Starts from the open waypoint nearest to Olimar and keeps only waypoints
    reachable on foot in both directions (there AND back) through open waypoints
    only: closed gates, unbuilt bridges and obstacles (waypoints closed by the
    game) cut the path. Water and "Pebble" waypoints are excluded, so no soft
    lock: Olimar can always come back.
    """
    graph = _read_waypoint_graph(game)
    if not graph:
        return None
    ox, oy, oz = origin

    def usable(i: int) -> bool:
        return graph[i]["open"] and not (graph[i]["flags"] & WP_FLAG_INWATER)

    # Start point: nearest usable waypoint (height is penalized so a point
    # above/below a cliff is not chosen).
    start, best = None, None
    for i, wp in enumerate(graph):
        if not usable(i):
            continue
        x, y, z = wp["pos"]
        d = (x - ox) ** 2 + (z - oz) ** 2 + 4.0 * (y - oy) ** 2
        if best is None or d < best:
            start, best = i, d
    if start is None:
        return None

    fwd_adj = [[] for _ in graph]
    rev_adj = [[] for _ in graph]
    for i, wp in enumerate(graph):
        if not usable(i):
            continue
        for j in wp["links"]:
            if usable(j):
                fwd_adj[i].append(j)
                rev_adj[j].append(i)

    def bfs(adj) -> set:
        seen, todo = {start}, [start]
        while todo:
            cur = todo.pop()
            for nxt in adj[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    todo.append(nxt)
        return seen

    both = bfs(fwd_adj) & bfs(rev_adj)
    candidates = [i for i in both if i != start and not (graph[i]["flags"] & WP_FLAG_PEBBLE)]
    if not candidates:
        return None
    import random as _random
    return graph[_random.choice(candidates)]["pos"]


def apply_teleport_trap(game: Game) -> bool:
    """Teleport Olimar to a safe waypoint (walkable both ways).

    If no safe point is found, returns False: the trap stays pending and is
    retried on the next tick.
    """
    navi = _resolve_olimar(game)
    if navi is None:
        return False
    addr = navi + NAVI_CHAIN["CREATURE_POSITION"]
    try:
        origin = struct.unpack(">fff", dme.read_bytes(addr, 12))
        dest = _safe_teleport_position(game, origin)
        if dest is None:
            return False
        x, y, z = dest
        dme.write_bytes(addr, struct.pack(">fff", x, y + TELEPORT_TRAP_LIFT, z))
        return True
    except Exception:
        return False


def _resolve_state_instance(navi: int, state_id: int) -> Optional[int]:
    """Pointer to the state instance `state_id`, via the StateMachine tables."""
    C = NAVI_CHAIN

    def u32(addr: int) -> Optional[int]:
        try:
            v = struct.unpack(">I", dme.read_bytes(addr, 4))[0]
        except Exception:
            return None
        return v if _RAM_MIN <= v < _RAM_MAX else None

    sm = u32(navi + C["NAVI_STATEMACHINE"])
    if sm is None:
        return None
    state_indexes = u32(sm + C["SM_STATEINDEXES"])
    states = u32(sm + C["SM_STATES"])
    if state_indexes is None or states is None:
        return None
    try:
        idx = struct.unpack(">i", dme.read_bytes(state_indexes + state_id * 4, 4))[0]
    except Exception:
        return None
    if idx < 0 or idx > 64:
        return None
    return u32(states + idx * 4)


async def apply_disband_trap(game: Game) -> bool:
    """Disband the squad deterministically.

    Uses the game's own mechanism:
      - NaviWalkState::exec transitions to NAVISTATE_Stuck as soon as
        Creature.mStickListHead is non-null;
      - NaviStuckState::init calls releasePikis(), which disperses the squad.
    The Walk state is forced and mStickListHead set non-null so the game performs
    the real transition and disband. mStickListHead is then reset to zero so
    Stuck::exec returns Olimar to Walk.
    """
    navi = _resolve_olimar(game)
    if navi is None:
        return False
    walk_state = _resolve_state_instance(navi, NAVISTATE_WALK)
    if walk_state is None:
        return False
    stick_addr = navi + NAVI_CHAIN["CREATURE_STICKLIST"]
    curr_addr = navi + NAVI_CHAIN["NAVI_CURRSTATE"]
    try:
        # Force the Walk state (so its exec runs) and prime the "stuck".
        # mStickListHead = navi: a valid non-null pointer (avoids a wild deref
        # if something reads it before it is reset to zero).
        dme.write_bytes(curr_addr, struct.pack(">I", walk_state))
        dme.write_bytes(stick_addr, struct.pack(">I", navi))
    except Exception:
        return False
    # Give the game a few frames to transition to Stuck and disperse.
    await asyncio.sleep(0.1)
    try:
        # Clear the list: Stuck::exec then returns Olimar to Walk.
        dme.write_bytes(stick_addr, struct.pack(">I", 0))
    except Exception:
        pass
    return True


# Synchronous appliers (single write). Disband is asynchronous (burst) and
# handled separately in apply_trap.
TRAP_APPLIERS = {
    "time":     apply_time_trap,
    "end_day":  apply_end_day_trap,
    "damage":   apply_damage_trap,
    "teleport": apply_teleport_trap,
}


# --- Trip Trap ------------------------------------------------------------
#
# Trip test (ActCrowd::exec, aiCrowd.cpp):
#     if (getRand(1.0f) >= 0.9999f && getRand(1.0f) > 0.7f) -> trip
# It is evaluated for each Pikmin following Olimar while running (> 110 u/s)
# every 100 units travelled. The Trip Trap replaces the 0.9999 constant (a copy
# private to this test in .sdata2, SYM_TRIP_RAND_CONST) with 0.0 for
# TRIP_TRAP_SECONDS: the first test is always true -> ~30% chance per test, so
# almost the whole moving squad trips (normal game animation, PIKIANIM_Korobu).
# Afterwards the normal value is restored (0.9999, or 2.0 if Trip Immunity is
# active). It is DATA, so Dolphin's JIT re-reads it.
# The timer only runs during interactive gameplay (not in pause/menus).

TRIP_TRAP_SECONDS = 10.0


def _trip_mode(ctx) -> int:
    """Disable Pikmin Trip option: 0 off, 1 always (patched ISO), 2 item."""
    slot_data = getattr(ctx, "slot_data", None) or {}
    return int(slot_data.get("disable_pikmin_trip", 1))


def _trip_immune(ctx) -> bool:
    """True if Pikmin can no longer trip (always mode, or item received)."""
    mode = _trip_mode(ctx)
    if mode == 1:
        return True
    if mode == 2:
        return any(it.item == TRIP_IMMUNITY_ITEM_ID for it in ctx.items_received)
    return False


def _trip_normal_value(ctx) -> float:
    return TRIP_DISABLED_FLOAT if _trip_immune(ctx) else TRIP_NORMAL_FLOAT


def apply_trip_trap(ctx, game: Game) -> bool:
    """Start (or restart) the Trip Trap. Always True: the trap is consumed."""
    if ctx is None:
        return False
    if _trip_immune(ctx):
        # Design choice: immunity (Trip Immunity item / always option) ->
        # the trap is consumed without effect.
        if ctx.debug_trap:
            logger.info("[DEBUG TRAP] Trip Trap has no effect: Pikmin are immune.")
        return True
    addr = SYM_TRIP_RAND_CONST.get(game)
    if addr is None:
        return True
    try:
        dme.write_bytes(addr, struct.pack(">f", TRIP_FORCED_FLOAT))
    except Exception:
        return False
    ctx._trip_trap_remaining = TRIP_TRAP_SECONDS
    ctx._trip_trap_last = time.monotonic()
    return True


def restore_trip_constant(ctx, game: Game) -> None:
    """Restore the trip constant to its normal value (trap end / shutdown)."""
    addr = SYM_TRIP_RAND_CONST.get(game)
    if addr is None:
        return
    try:
        dme.write_bytes(addr, struct.pack(">f", _trip_normal_value(ctx)))
    except Exception:
        pass


async def handle_trip_trap_timer(ctx, game: Game) -> None:
    """Count down the Trip Trap and restore the constant."""
    addr = SYM_TRIP_RAND_CONST.get(game)
    if addr is None:
        return
    if ctx._trip_trap_remaining <= 0:
        # Safety: constant left forced (client closed during a trap,
        # reconnection...) -> restore it.
        try:
            if dme.read_bytes(addr, 4) == struct.pack(">f", TRIP_FORCED_FLOAT):
                restore_trip_constant(ctx, game)
        except Exception:
            pass
        return
    now = time.monotonic()
    dt = now - ctx._trip_trap_last
    ctx._trip_trap_last = now
    if is_in_level(game) and is_day_active(game) and not is_overlay_active(game):
        ctx._trip_trap_remaining -= dt
    if ctx._trip_trap_remaining <= 0 or _trip_immune(ctx):
        ctx._trip_trap_remaining = 0.0
        restore_trip_constant(ctx, game)
        if ctx.debug_trap:
            logger.info("[DEBUG TRAP] Trip Trap finished.")
    else:
        try:
            dme.write_bytes(addr, struct.pack(">f", TRIP_FORCED_FLOAT))
        except Exception:
            pass


# --- DeathLink messages according to the cause of death -------------------------
# vtables of the interactions that hurt Olimar (config/*/symbols.txt) -> type.
DAMAGE_VTABLES = {
    b"GPIP01": {0x802AF6C4: "attack", 0x802AF67C: "swallow", 0x802AF5EC: "press",
                0x802AF758: "flick", 0x802AF7E8: "fire", 0x802AF830: "bubble", 0x802D007C: "bomb"},
    b"GPIE01": {0x802ACE04: "attack", 0x802ACDBC: "swallow", 0x802ACD2C: "press",
                0x802ACE98: "flick", 0x802ACF28: "fire", 0x802ACF70: "bubble", 0x802CD9EC: "bomb"},
}
TEKI_TYPE_OFF = 0x320  # Teki::mTekiType (include/Teki.h)
OBJTYPE_TEKI = 55
OBJTYPE_BOMB = 14
TEKI_NAMES = {  # enum TekiTypes (include/teki.h), PAL names
    0: "Yellow Wollyhop", 2: "Rolling Boulder", 3: "Dwarf Bulborb", 4: "Spotty Bulborb",
    6: "Honeywisp", 8: "Breadbug", 9: "Puffstool", 10: "Pearly Clamclamp",
    11: "Swooping Snitchbug", 13: "Pearly Clamclamp", 14: "Pearly Clamclamp",
    15: "Fiery Blowhog", 16: "Puffy Blowhog", 17: "Armored Cannon Beetle",
    18: "Female Sheargrub", 19: "Male Sheargrub", 20: "Shearwig", 22: "Smoky Progg",
    23: "Fire Geyser", 24: "Mamuta", 25: "Wolpole", 30: "Water Dumple",
    31: "Dwarf Bulbear", 32: "Spotty Bulbear", 33: "Wollyhop",
}
BOSS_NAMES = {  # enum ObjType (include/ObjType.h)
    39: "Beady Long Legs", 41: "Burrowing Snagret", 43: "Emperor Bulblax", 44: "Goolix",
    45: "Iridescent Flint Beetle", 46: "Candypop Bud", 48: "Goolix",
}
DEATH_MSG = {
    "killed":   {"en": "{name} was killed by {enemy}.", "fr": "{name} a été tué par {enemy}.",
                 "de": "{name} wurde von {enemy} getötet.", "it": "{name} è stato ucciso da {enemy}.",
                 "es": "{name} fue asesinado por {enemy}."},
    "eaten":    {"en": "{name} was eaten by {enemy}.", "fr": "{name} a été dévoré par {enemy}.",
                 "de": "{name} wurde von {enemy} gefressen.", "it": "{name} è stato divorato da {enemy}.",
                 "es": "{name} fue devorado por {enemy}."},
    "crushed":  {"en": "{name} was crushed by {enemy}.", "fr": "{name} a été écrasé par {enemy}.",
                 "de": "{name} wurde von {enemy} zerquetscht.", "it": "{name} è stato schiacciato da {enemy}.",
                 "es": "{name} fue aplastado por {enemy}."},
    "flung":    {"en": "{name} was sent flying by {enemy}.", "fr": "{name} a été projeté par {enemy}.",
                 "de": "{name} wurde von {enemy} weggeschleudert.",
                 "it": "{name} è stato scaraventato via da {enemy}.", "es": "{name} salió volando por {enemy}."},
    "burned":   {"en": "{name} burned to death.", "fr": "{name} est mort brûlé.", "de": "{name} ist verbrannt.",
                 "it": "{name} è morto bruciato.", "es": "{name} murió quemado."},
    "burned_by": {"en": "{name} was burned to death by {enemy}.", "fr": "{name} a été brûlé vif par {enemy}.",
                  "de": "{name} wurde von {enemy} verbrannt.", "it": "{name} è stato bruciato vivo da {enemy}.",
                  "es": "{name} fue quemado vivo por {enemy}."},
    "explosion": {"en": "{name} died in an explosion.", "fr": "{name} est mort dans une explosion.",
                  "de": "{name} starb bei einer Explosion.", "it": "{name} è morto in un'esplosione.",
                  "es": "{name} murió en una explosión."},
    "grief":    {"en": "{name} died of grief over the loss of so many Pikmin.",
                 "fr": "{name} est mort de chagrin après la perte de tant de Pikmin.",
                 "de": "{name} starb vor Kummer über den Verlust so vieler Pikmin.",
                 "it": "{name} è morto di dolore per la perdita di così tanti Pikmin.",
                 "es": "{name} murió de pena por la pérdida de tantos Pikmin."},
    "lost":     {"en": "{name} was lost on the planet.", "fr": "{name} s'est perdu sur la planète.",
                 "de": "{name} ging auf dem Planeten verloren.", "it": "{name} si è perso sul pianeta.",
                 "es": "{name} se perdió en el planeta."},
    "trap_from": {"en": "{name} was taken down by a Damage Trap from {source}.",
                  "fr": "{name} a été terrassé par un Damage Trap de {source}.",
                  "de": "{name} wurde von einer Damage Trap von {source} niedergestreckt.",
                  "it": "{name} è stato abbattuto da una Damage Trap di {source}.",
                  "es": "{name} fue derribado por una Damage Trap de {source}."},
    "trap":     {"en": "{name} was taken down by the Damage Trap.",
                 "fr": "{name} a été terrassé par le Damage Trap.",
                 "de": "{name} wurde von der Damage Trap niedergestreckt.",
                 "it": "{name} è stato abbattuto dalla Damage Trap.",
                 "es": "{name} fue derribado por la Damage Trap."},
}
# Official translated names (Pikipedia, "Names in other languages"), already
# inflected with the article/case used in DEATH_MSG. Enemies not listed
# (Fire Geyser, Rolling Boulder: no official translated name) stay in English.
ENEMY_I18N = {
    "Dwarf Bulborb":           {"fr": "un Bulborbe nain", "de": "einem Zwerg-Punktkäfer", "it": "un Coleto nano", "es": "un Bulbo enano"},
    "Spotty Bulborb":          {"fr": "un Bulborbe à pois", "de": "einem Punktkäfer", "it": "un Coleto", "es": "un Bulbo Moteado"},  # page Bulborb
    "Dwarf Bulbear":           {"fr": "un Bulbours Nain", "de": "einem Zwerg-Punktbär", "it": "un Coleto nano macchiato", "es": "un Bulboso enano"},
    "Spotty Bulbear":          {"fr": "un Bulbours à pois", "de": "einem Getupften Punktbär", "it": "un Coleto Macchiato", "es": "un Bulboso moteado"},
    "Yellow Wollyhop":         {"fr": "un Wog jaune", "de": "einem Gelben Orcalog", "it": "una Ranuca idropica gialla", "es": "un Sapo gigante amarillo"},
    "Wollyhop":                {"fr": "un Wog Sauteur", "de": "einem Orcalog", "it": "una Ranuca idropica", "es": "un Sapo gigante"},
    "Wolpole":                 {"fr": "un Wog Larvaire", "de": "einer Wackelquappe", "it": "una Ranuchetta", "es": "un Sapicuajo"},
    "Honeywisp":               {"fr": "un Mouchamiel", "de": "einer Nektarelfe", "it": "una Vespa nettarice", "es": "un Agarramiel"},
    "Breadbug":                {"fr": "un Scaratax", "de": "einem Diebischen Saprophag", "it": "un Saprofago", "es": "una Chinche Carroñera"},
    "Puffstool":               {"fr": "un Champispore", "de": "einer Puffmorchel", "it": "un'Amanita panciuta", "es": "una Seta de esporas"},
    "Pearly Clamclamp":        {"fr": "une Coquiperle", "de": "einer Amphibienauster", "it": "un Chelus perlato", "es": "un Bivalvo Opalescente"},
    "Swooping Snitchbug":      {"fr": "un Piquépille", "de": "einem Flatternden Piknapper", "it": "un Dittero ladro", "es": "un Moscardón ladrón"},
    "Fiery Blowhog":           {"fr": "un Crachefeu", "de": "einem Rüsselignis", "it": "un Eruptor igneo", "es": "un Verraco dragón"},
    "Puffy Blowhog":           {"fr": "un Puffy Volant", "de": "einem Ballonerus", "it": "una Moschita Vacua", "es": "un Verraco volador"},
    "Armored Cannon Beetle":   {"fr": "un Scaracanon Blindé", "de": "einem Crustabitze", "it": "uno Scarabeo Corazzato", "es": "un Escarabajo Tirador"},
    "Female Sheargrub":        {"fr": "un Boufpon femelle", "de": "einem Weiblichen Termitentos", "it": "un Tarlo molare femmina", "es": "un Comején hembra"},
    "Male Sheargrub":          {"fr": "un Boufpon mâle", "de": "einem Männlichen Termitentos", "it": "un Tarlo molare maschio", "es": "un Comején macho"},
    "Shearwig":                {"fr": "un Boufpon Volant", "de": "einem Scherenzopf", "it": "un Tarlo alato", "es": "un Comején volador"},
    "Smoky Progg":             {"fr": "un Molosko Fumant", "de": "einem Dilabovum", "it": "un Gassovo", "es": "un Cigoto Fumoso"},
    "Mamuta":                  {"fr": "un Mamuta", "de": "einem Mamuta", "it": "un Mamuta", "es": "un Mamuta"},
    "Water Dumple":            {"fr": "un Bouledeau", "de": "einem Wasser-Klößling", "it": "un'Idrotalpa", "es": "una Mole acuática"},
    "Beady Long Legs":         {"fr": "un Baba Longues jambes", "de": "einem Perligen Langbein", "it": "un Longopede", "es": "una Pelota patas largas"},
    "Burrowing Snagret":       {"fr": "un Snabrek Fouisseur", "de": "einem Gemeinen Schnapper", "it": "una Vermentilla squamata", "es": "un Tagarote escurridizo"},
    "Emperor Bulblax":         {"fr": "un Bulblax Empereur", "de": "einem Fürst Knollenauge", "it": "un Bulbico Imperiale", "es": "un Bulbo emperador"},
    "Goolix":                  {"fr": "un Bavox", "de": "einem Golemgel", "it": "un Bigelico", "es": "un Mocrobio"},
    "Iridescent Flint Beetle": {"fr": "un Scarabée Iridescent", "de": "einem Psychilex", "it": "un Iridococco", "es": "un Escarabajo de sílex iridiscente"},
    "Candypop Bud":            {"fr": "une Fleur Cracheuse", "de": "einer Königinblume", "it": "una Cromanvillea", "es": "un Brote rebotador"},
}
_ARTICLE = {"en": lambda e: ("an " if e[0] in "AEIOU" else "a ") + e,
            "fr": lambda e: "un " + e, "de": lambda e: "einem " + e,
            "it": lambda e: "un " + e, "es": lambda e: "un " + e}


def death_message(ctx, kind: str, enemy: Optional[str] = None, source: Optional[str] = None) -> str:
    """DeathLink message in the detected game language."""
    lang = getattr(ctx, "detected_language", "en") or "en"
    table = DEATH_MSG.get(kind, DEATH_MSG["lost"])
    text = table.get(lang, table["en"])
    name = ctx.player_names.get(ctx.slot, "Olimar")
    if not enemy:
        enemy_txt = ""
    elif lang in ENEMY_I18N.get(enemy, {}):
        enemy_txt = ENEMY_I18N[enemy][lang]  # official translated name, article included
    else:
        enemy_txt = _ARTICLE.get(lang, _ARTICLE["en"])(enemy)
    return text.format(name=name, enemy=enemy_txt, source=source or "")


def _creature_name(owner: int) -> tuple[Optional[str], int]:
    """Return (creature name, mObjType) from a Creature*."""
    if not (_RAM_MIN <= owner < _RAM_MAX):
        return None, -1
    try:
        obj = struct.unpack(">i", dme.read_bytes(owner + ONION_CHAIN["CREATURE_OBJTYPE"], 4))[0]
        if obj == OBJTYPE_TEKI:
            t = struct.unpack(">i", dme.read_bytes(owner + TEKI_TYPE_OFF, 4))[0]
            return TEKI_NAMES.get(t), obj
        return BOSS_NAMES.get(obj), obj
    except Exception:
        return None, -1


def olimar_death_message(ctx, game: Game) -> str:
    """Message based on the last hit Olimar received (buffer from the ISO patch)."""
    ring = getattr(ctx, "death_cause_ring", None)
    vt = DAMAGE_VTABLES.get(game, {})
    if ring is None or not vt:
        return death_message(ctx, "lost")
    try:
        raw = dme.read_bytes(ring, 4 + 4 * 8)
    except Exception:
        return death_message(ctx, "lost")
    idx = struct.unpack_from(">I", raw, 0)[0] & 3
    for k in range(4):  # from most recent to oldest
        e = (idx - k) & 3
        vtable, owner = struct.unpack_from(">II", raw, 4 + e * 8)
        kind = vt.get(vtable)
        if kind is None:
            continue
        if kind == "bomb":
            return death_message(ctx, "explosion")
        enemy, obj = _creature_name(owner)
        if kind == "fire":
            # Fire source if known (Fiery Blowhog, Fire Geyser...).
            return death_message(ctx, "burned_by", enemy) if enemy else death_message(ctx, "burned")
        if obj == OBJTYPE_BOMB:
            return death_message(ctx, "explosion")
        if not enemy:
            return death_message(ctx, "lost")
        msg_kind = {"swallow": "eaten", "press": "crushed", "flick": "flung"}.get(kind, "killed")
        return death_message(ctx, msg_kind, enemy)
    return death_message(ctx, "lost")


async def report_client_kill(ctx) -> None:
    """Send the DeathLink for an Olimar death caused by the client
    (Damage Trap, Olimar/Pikmin bond).

    The "classic" detection (rising edge of orimaDead in handle_death_link)
    only runs during interactive gameplay, but death immediately stops
    gameplay (start of the end-of-day sequence), so the edge would never be
    seen. The DeathLink is therefore sent directly, and the detection is
    suppressed so it is not sent a second time.
    """
    reason = getattr(ctx, "_client_kill_reason", None) or "the client"
    ctx._client_kill_reason = None
    # Originating player (Damage Trap: slot that sent the trap / TrapLink source).
    source = getattr(ctx, "_trap_source", None) if reason == "Damage Trap" else None
    ctx._suppress_orima_send = True
    if getattr(ctx, "death_link_mode", 0) not in (1, 3):  # classic / both
        return
    if getattr(ctx, "_deathlink_locked_this_day", False):
        return
    if reason == "Pikmin Bond":
        await ctx.send_death(death_message(ctx, "grief"))
    elif source:
        await ctx.send_death(death_message(ctx, "trap_from", source=source))
    else:
        await ctx.send_death(death_message(ctx, "trap"))
    ctx._deathlink_locked_this_day = True


async def apply_trap(game: Game, kind: str, ctx=None) -> bool:
    """Apply a trap by internal kind. Return True if applied."""
    if kind == "disband":
        return await apply_disband_trap(game)
    if kind == "trip":
        return apply_trip_trap(ctx, game)
    if kind == "damage":
        ok = apply_damage_trap(game, ctx)
        if ok and ctx is not None and getattr(ctx, "_client_kill_reason", None):
            await report_client_kill(ctx)
        return ok
    fn = TRAP_APPLIERS.get(kind)
    return bool(fn and fn(game))


def read_game_language(game: Game) -> Optional[str]:
    """Return the current language code, or None if unreadable.

    Any unexpected value (null pointer, out of RAM, ID outside the enum) returns
    None rather than a wrong language: the caller then keeps the previous value.
    """
    if game != b"GPIP01":
        # NTSC-U (and anything else): English only.
        return "en"

    gsys_ptr_addr = SYM_GSYS_PTR.get(game)
    if gsys_ptr_addr is None:
        return None

    try:
        gsys = struct.unpack(">I", dme.read_bytes(gsys_ptr_addr, 4))[0]
        if not (_RAM_MIN <= gsys < _RAM_MAX):
            return None  # not yet initialized at the very start of boot
        lang_id = struct.unpack(
            ">I", dme.read_bytes(gsys + STDSYSTEM_LANGUAGE_OFFSET, 4)
        )[0]
    except Exception:
        return None

    return LANGUAGE_IDS.get(lang_id)

# Official in-game ship part names per language.
# Key = English name (as used in ALL_PARTS), value = dict lang -> bytes (latin-1).
# Order in list: fr, de, it, es
SHIP_PART_TRANSLATIONS: dict[str, dict[str, bytes]] = {
    "Main Engine":         {"fr": b"Moteur Principal",       "de": b"Hauptantrieb des Dolphins", "it": b"Motore principale",    "es": b"Motor principal del Dolphin"},
    "Positron Generator":  {"fr": b"Positronator",           "de": b"Positron-Generator",        "it": b"Generat. positroni",    "es": b"Positronador"},
    "Eternal Fuel Dynamo": {"fr": b"G\xe9n\xe9rateur Infini","de": b"Kraftstoff-Dynamo",          "it": b"Dinamo perenne",        "es": b"Dinamo"},
    "Extraordinary Bolt":  {"fr": b"Super Boulon",           "de": b"Au\xdfergwl. Schraube",     "it": b"Vite straordinaria",    "es": b"Perno de aleci\xf3n"},
    "Whimsical Radar":     {"fr": b"Radar Bizarre",          "de": b"Sonderbar-Radar",           "it": b"Super radar",           "es": b"Radar Enigm\xe1tico"},
    "Geiger Counter":      {"fr": b"Compteur Geiger",        "de": b"Geigenz\xe4hler",           "it": b"Contatore Geiger",      "es": b"Contador Geiger"},
    "Radiation Canopy":    {"fr": b"Cockpit NBC",            "de": b"Strahlenschutz",            "it": b"Calotta radiazioni",    "es": b"C\xe1psula protectora"},
    "Sagittarius":         {"fr": b"Sagittaire",             "de": b"Der Sch\xfctze",            "it": b"Sagittario",            "es": b"Sagitario"},
    "Shock Absorber":      {"fr": b"Absorbeur de Choc",      "de": b"Sto\xdfd\xe4mpfer",         "it": b"Assorbishock",          "es": b"Amortiguador"},
    "Automatic Gear":      {"fr": b"Bo\xeete Automatique",   "de": b"Autom. Getriebe",           "it": b"Autonavigatore",        "es": b"Transmisi\xf3n"},
    "#1 Ionium Jet":       {"fr": b"Propulseur 1",           "de": b"Ionenjet Nr.1",             "it": b"Jet ionio 1",           "es": b"Reactor I\xf3nico n.\xb0 1"},
    "Anti-Dioxin Filter":  {"fr": b"Filtre \xe0 Dioxine",   "de": b"Dioxin-Filter",             "it": b"Anti diossina",         "es": b"Filtro anti-dioxinas"},
    "Omega Stabilizer":    {"fr": b"Stabilisateur Om\xe9ga", "de": b"Omega-Stabilisator",        "it": b"Stabilizzat. omega",    "es": b"Estabilizador Omega"},
    "Gravity Jumper":      {"fr": b"Unit\xe9 Antigrav",      "de": b"Gravitationsblocker",       "it": b"Propulsore gravit\xe0",  "es": b"Anti-gravitador"},
    "Analog Computer":     {"fr": b"Intelligence Artificielle", "de": b"Analoger Computer",      "it": b"Computer analogico",    "es": b"Sistema Anal\xf3gico"},
    "Guard Satellite":     {"fr": b"Satellite de Garde",     "de": b"W\xe4chter-Satellit",       "it": b"Satellite guardia",     "es": b"Sat\xe9lite"},
    "Libra":               {"fr": b"Balance",                "de": b"Die Waage",                 "it": b"Bilancia",              "es": b"Libra"},
    # Mind the case: the key must match ALL_PARTS (P1Data.py) EXACTLY.
    "Repair-type Bolt":    {"fr": b"Boulon de Secours",      "de": b"Reparatur-Bolzen",          "it": b"Bullone riparazione",   "es": b"Perno reparador"},
    "Gluon Drive":         {"fr": b"Unit\xe9 Gluonique",     "de": b"Gluon-Antrieb",             "it": b"Unit\xe0 a gluoni",     "es": b"Emisor de gluones"},
    "Zirconium Rotor":     {"fr": b"Rotor Zirconium",        "de": b"Zirkonium-Rotor",           "it": b"Rotore zirconio",       "es": b"Rotor de zirconio"},
    "Interstellar Radio":  {"fr": b"Radio Stellaire",        "de": b"Interstellar-Radio",        "it": b"Radio interstellare",   "es": b"Radio interestelar"},
    "Pilot's Seat":        {"fr": b"Si\xe8ge du Pilote",     "de": b"Pilotensitz",               "it": b"Sedile pilota",         "es": b"Asiento de piloto"},
    "#2 Ionium Jet":       {"fr": b"Propulseur 2",           "de": b"Ionenjet Nr.2",             "it": b"Jet ionio 2",           "es": b"Reactor I\xf3nico n.\xb0 2"},
    "Bowsprit":            {"fr": b"Beaupr\xe9",             "de": b"Bugspriet",                 "it": b"Bompresso",             "es": b"Baupr\xe9s"},
    "Chronos Reactor":     {"fr": b"R\xe9acteur Chronos",    "de": b"Kr\xfcmmungsreaktor",       "it": b"Cronoreattore",         "es": b"Reactor Chronos"},
    "Nova Blaster":        {"fr": b"Missile Nova",           "de": b"Nova-Blaster",              "it": b"Polverizzatore",        "es": b"Detonador Nova"},
    "Space Float":         {"fr": b"Bou\xe9e Spatiale",      "de": b"Levita-Reifen",             "it": b"Galleggiante",          "es": b"Flotador espacial"},
    "Massage Machine":     {"fr": b"Si\xe8ge de Massage",    "de": b"Massageeinheit",            "it": b"Macchina massaggi",     "es": b"M\xe1quina de masajes"},
    "UV Lamp":             {"fr": b"Lampe \xe0 UV",          "de": b"UV-Lampe",                  "it": b"Lampada UV",            "es": b"L\xe1mpara de UV"},
    "Secret Safe":         {"fr": b"Coffre Secret",          "de": b"Geheimsafe",                "it": b"Cassaforte",            "es": b"Caja fuerte"},
}

# Translated languages (English uses the ALL_PARTS keys directly).
TRANSLATED_LANGS = ("fr", "de", "it", "es")


def _check_translation_tables() -> list[str]:
    """Check that every ALL_PARTS entry has a translation for each language.

    A case mismatch in a key would silently disable the translation of a part
    in hint mode, so any gap is reported at startup.
    """
    problems: list[str] = []
    for part_name in ALL_PARTS:
        entry = SHIP_PART_TRANSLATIONS.get(part_name)
        if entry is None:
            problems.append(f"no translation for part {part_name!r}")
            continue
        for lang in TRANSLATED_LANGS:
            if not entry.get(lang):
                problems.append(f"{part_name!r} : traduction {lang} manquante")
    for key in SHIP_PART_TRANSLATIONS:
        if key not in ALL_PARTS:
            problems.append(f"cle de traduction {key!r} inconnue de ALL_PARTS")
    return problems


# Hint labels, per language.
HINT_LABELS: dict[str, dict[str, str]] = {
    "en": {"contains": "Contains:", "for": "For:",
           "at": "Your Ship Part is at", "in": "in", "none": "No hint data"},
    "fr": {"contains": "Contient :", "for": "Pour :",
           "at": "Votre pièce est à", "in": "chez", "none": "Aucun indice"},
    "de": {"contains": "Enthält:", "for": "Für:",
           "at": "Dein Schiffsteil ist in", "in": "bei", "none": "Kein Hinweis"},
    "it": {"contains": "Contiene:", "for": "Per:",
           "at": "Il tuo pezzo è a", "in": "da", "none": "Nessun indizio"},
    "es": {"contains": "Contiene:", "for": "Para:",
           "at": "Tu pieza está en", "in": "de", "none": "Sin pista"},
}


def _labels(lang: str) -> dict[str, str]:
    return HINT_LABELS.get(lang, HINT_LABELS["en"])


def _part_display_name(part_name: str, lang: str) -> str:
    """Part name in the detected language, falling back to English."""
    if lang == "en":
        return part_name
    translated = SHIP_PART_TRANSLATIONS.get(part_name, {}).get(lang)
    if translated:
        return translated.decode("latin-1")
    return part_name


def _encode_hint(text: str) -> bytes:
    """Encode hint text for the game's text engine.

    The game uses latin-1, so accents (player/item names, translated labels)
    are preserved instead of being turned into '?'.
    """
    result = text.encode("latin-1", errors="replace")
    if len(result) > SHIP_PART_TEXT_LENGTH:
        result = result[:SHIP_PART_TEXT_LENGTH]
    if len(result) < SHIP_PART_TEXT_LENGTH:
        result += b"\x00" * (SHIP_PART_TEXT_LENGTH - len(result))
    return result


# ---------------------------------------------------------------------------
# Addresses derived from the decompilation (projectPiki/pikmin) via P1Symbols.py.
# Both PAL and NTSC-U are provided for all the tables below.
# ---------------------------------------------------------------------------

# formationPikis__8GameStat -- low byte of the u32 (big-endian).
# Used for the location check.
PIKMIN_ADDRESSES = SYM_PIKMIN_ADDRESSES

# GameStat::containerPikis__8GameStat -- live total per color (Pikmin currently
# "in an onion"), updated by the game in real time whenever a Piki enters/leaves
# an onion (goalItem.cpp, itemAI.cpp).
ONION_DYN_ADDRS = SYM_ONION_DYN_ADDRS

# GameStat::allPikis__8GameStat -- the total actually shown on the HUD
# (bottom-right overall counter) and on the results screen, via
# zen::pGameInfo->mTotalPikiNum = GameStat::allPikis (gameCoreSection.cpp).
# Only recomputed when GameStat::update() runs (real game events: a Piki
# entering/leaving an onion, formation, etc., or once per day on level load),
# never continuously from pikiInfMgr.mPikiCounts. Writing only STAGE therefore
# changes nothing until the game redoes this computation itself.
GAMESTAT_ALLPIKIS_ADDRS = SYM_ALLPIKIS_ADDRS

# Start-of-day sentinel: gameflow+0x2EC (0 in menus, non-zero in game).
ONION_DYN_SENTINEL = _gf("SENTINEL")

# pikiInfMgr.mPikiCounts[color][stage], u32 each.
# The game recomputes the displayed total itself = Leaf + Bud + Flower.
ONION_STAGE_ADDRS_CLIENT = SYM_ONION_STAGE_ADDRS


class P1CommandProcessor(SuperCommandProcessor):
    def __init__(self, ctx: CommonContext):
        super().__init__(ctx)

    def _cmd_debugwrites(self) -> bool:
        """Toggle logging of every RAM write made by the client."""
        self.ctx.debug_writes = not getattr(self.ctx, "debug_writes", False)
        dme.trace_writes = self.ctx.debug_writes
        logger.info(f"[DEBUG] RAM write logging: {'ON' if self.ctx.debug_writes else 'OFF'}")
        return True

    def _cmd_nowrites(self) -> bool:
        """Toggle blocking of every RAM write made by the client (diagnostic)."""
        dme.block_writes = not dme.block_writes
        logger.info(f"[DEBUG] RAM writes blocked: {'ON' if dme.block_writes else 'OFF'}")
        return True

    def _cmd_debughint(self) -> bool:
        """Toggle debug logging for hint-related messages."""
        self.ctx.debug_hint = not getattr(self.ctx, "debug_hint", False)
        state = "ON" if self.ctx.debug_hint else "OFF"
        logger.info(f"[DEBUG] Hint debug: {state}")
        if self.ctx.debug_hint:
            slot_data = getattr(self.ctx, "slot_data", {}) or {}
            hint_mode = slot_data.get("ship_part_hint_mode", 0)
            hints = slot_data.get("hints", {})
            logger.info(f"[DEBUG HINT] Hint mode: {hint_mode}")
            logger.info(f"[DEBUG HINT] Hints count: {len(hints)}")
            if hints:
                for part_name, hint_data in hints.items():
                    logger.info(f"[DEBUG HINT]   {part_name}: {hint_data.get('Item', '?')} at {hint_data.get('Location', '?')}")
        return True

    def _cmd_debugdays(self) -> bool:
        """Toggle debug logging for day cycle messages."""
        self.ctx.debug_days = not getattr(self.ctx, "debug_days", False)
        state = "ON" if self.ctx.debug_days else "OFF"
        logger.info(f"[DEBUG] Day cycle debug: {state}")
        if self.ctx.debug_days:
            slot_data = getattr(self.ctx, "slot_data", {}) or {}
            mode = slot_data.get("day_cycle_mode", 0)
            logger.info(f"[DEBUG DAYS] Day cycle mode: {mode}")
        return True

    def _cmd_debugpbonus(self) -> bool:
        """Toggle debug logging for Pikmin bonus item messages."""
        self.ctx.debug_pbonus = not getattr(self.ctx, "debug_pbonus", False)
        state = "ON" if self.ctx.debug_pbonus else "OFF"
        logger.info(f"[DEBUG] Pikmin bonus debug: {state}")
        if self.ctx.debug_pbonus:
            applied = _named_counts(getattr(self.ctx, "pikmin_items_applied", {}))
            if applied:
                logger.info("[DEBUG PBONUS] Applied items:")
                for name, n in applied.items():
                    logger.info(f"[DEBUG PBONUS]   {name}: {n}")
            else:
                logger.info("[DEBUG PBONUS] Applied items: (none)")
        return True

    def _cmd_debugtrap(self) -> bool:
        """Toggle debug logging for trap and TrapLink messages."""
        self.ctx.debug_trap = not getattr(self.ctx, "debug_trap", False)
        state = "ON" if self.ctx.debug_trap else "OFF"
        logger.info(f"[DEBUG] Trap / TrapLink debug: {state}")
        if self.ctx.debug_trap:
            logger.info(f"[DEBUG TRAP] TrapLink enabled: {getattr(self.ctx, 'trap_link_enabled', False)} "
                        f"| tags: {sorted(getattr(self.ctx, 'tags', []))}")
            traps = getattr(self.ctx, "traps_applied", {})
            named = {_TRAP_KIND_TO_NAME.get(_TRAP_ID_TO_KIND.get(k, ""), f"#{k}"): v
                     for k, v in traps.items()}
            logger.info(f"[DEBUG TRAP] Traps applied: {named or '(none)'}")
            logger.info(f"[DEBUG TRAP] Pending TrapLink: {getattr(self.ctx, 'pending_trap_links', [])}")
        return True

    def _cmd_debuglanguage(self) -> bool:
        """Show the language currently detected by the client."""
        lang = getattr(self.ctx, "detected_language", "en")
        logger.info(f"[DEBUG LANGUAGE] Language: {LANG_NAMES.get(lang, lang)} ({lang})")

        if not dme.is_hooked():
            logger.info("[DEBUG LANGUAGE] Dolphin not connected — live read unavailable.")
            return True

        try:
            game = dme.read_bytes(0x80000000, 6)
        except Exception as e:
            logger.info(f"[DEBUG LANGUAGE] Could not read Game ID: {e}")
            return True

        base_id = BASE_ID_BY_PATCHED_PREFIX.get(game[:3], game)
        logger.info(f"[DEBUG LANGUAGE] Game ID: {game!r} (base {base_id.decode(errors='replace')})")
        if base_id != b"GPIP01":
            logger.info("[DEBUG LANGUAGE] Non-PAL version: English only, "
                        "gsys->mLanguageID does not exist.")
            return True

        gsys_ptr_addr = SYM_GSYS_PTR.get(base_id)
        try:
            gsys = struct.unpack(">I", dme.read_bytes(gsys_ptr_addr, 4))[0]
            logger.info(f"[DEBUG LANGUAGE] gsys @ 0x{gsys_ptr_addr:08X} -> 0x{gsys:08X}")
            if not (_RAM_MIN <= gsys < _RAM_MAX):
                logger.info("[DEBUG LANGUAGE] gsys pointer out of RAM (game not initialized yet).")
                return True
            addr = gsys + STDSYSTEM_LANGUAGE_OFFSET
            lang_id = struct.unpack(">I", dme.read_bytes(addr, 4))[0]
            logger.info(f"[DEBUG LANGUAGE] mLanguageID @ 0x{addr:08X} = {lang_id} "
                        f"-> {LANGUAGE_IDS.get(lang_id, '??? (out of enum)')}")
        except Exception as e:
            logger.info(f"[DEBUG LANGUAGE] Read error: {e}")
        return True

    def _cmd_debugtext(self) -> bool:
        """Follow the pointer chain to the on-screen text and compare with the known PAL address."""
        if not dme.is_hooked():
            logger.info("[DEBUG TEXT] Dolphin not connected.")
            return True

        try:
            game = dme.read_bytes(0x80000000, 6)
        except Exception as e:
            logger.info(f"[DEBUG TEXT] Could not read Game ID: {e}")
            return True

        base_id = BASE_ID_BY_PATCHED_PREFIX.get(game[:3], game)
        if base_id != game:
            logger.info(f"[DEBUG TEXT] Patched ISO ({game.decode()}) "
                        f"— original version {base_id.decode()}.")
        logger.info(f"[DEBUG TEXT] Game ID: {game!r}")

        tw_addr = SYM_TUTORIAL_WINDOW_PTR.get(base_id)
        if tw_addr is None:
            logger.info(f"[DEBUG TEXT] Unknown version: {base_id!r}")
            return True

        def u32(addr: int) -> int:
            return struct.unpack(">I", dme.read_bytes(addr, 4))[0]

        try:
            tut = u32(tw_addr)
            logger.info(f"[DEBUG TEXT] tutorialWindow @ 0x{tw_addr:08X} -> 0x{tut:08X}")
            if not (_RAM_MIN <= tut < _RAM_MAX):
                logger.info("[DEBUG TEXT] Null/invalid pointer: no text currently "
                            "displayed. Open a ship part's text, then run again.")
                return True

            msgmgr = u32(tut + TUTORIAL_TEXT_CHAIN["TUTORIALMGR_MESSAGEMGR"])
            logger.info(f"[DEBUG TEXT] mMessageMgr -> 0x{msgmgr:08X}")
            if not (_RAM_MIN <= msgmgr < _RAM_MAX):
                logger.info("[DEBUG TEXT] mMessageMgr invalid.")
                return True

            text_addr = msgmgr + TUTORIAL_TEXT_CHAIN["MSGMGR_FORMATTED"]
            logger.info(f"[DEBUG TEXT] formatted text @ 0x{text_addr:08X}")
            logger.info(f"[DEBUG TEXT] hardcoded PAL address = 0x{SHIP_PART_TEXT_ADDR:08X} "
                        f"(offset = {text_addr - SHIP_PART_TEXT_ADDR:+d})")

            raw = dme.read_bytes(text_addr, 96)
            printable = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in raw)
            logger.info(f"[DEBUG TEXT] content: {printable}")

            msg_id = read_displayed_message_id(msgmgr)
            kind = "none"
            if msg_id is not None:
                for k in ("discovery", "info", "collect", "power"):
                    base = TUT_PART_TEXT_RANGES[k]
                    if base <= msg_id < base + len(UFO_PART_ORDER):
                        kind = k
                        break
            logger.info(f"[DEBUG TEXT] message ID (EnumTutorial) = {msg_id} "
                        f"| part range: {kind}")
            logger.info(f"[DEBUG TEXT] detected part: {read_displayed_part(base_id)}")
        except Exception as e:
            logger.info(f"[DEBUG TEXT] Read error: {e}")
        return True

    def _cmd_debugsave(self) -> bool:
        """Show whether the client considers a save file to be loaded."""
        if not dme.is_hooked():
            logger.info("[DEBUG SAVE] Dolphin not connected.")
            return True
        try:
            game = dme.read_bytes(0x80000000, 6)
        except Exception as e:
            logger.info(f"[DEBUG SAVE] Could not read Game ID: {e}")
            return True
        base_id = BASE_ID_BY_PATCHED_PREFIX.get(game[:3], game)
        gf = SYM_GAMEFLOW.get(base_id)
        if not gf:
            logger.info(f"[DEBUG SAVE] Unknown version: {base_id!r}")
            return True
        def u32(addr):
            return struct.unpack(">I", dme.read_bytes(addr, 4))[0]

        try:
            section = struct.unpack(">i", dme.read_bytes(gf["GAME_SECTION"], 4))[0]
            subsection = struct.unpack(">i", dme.read_bytes(gf["ONEPLAYER_SECTION"], 4))[0]
            day = dme.read_byte(DAY_NUMBER[base_id])
            sentinel = u32(gf["SENTINEL"])
            item_mgr = u32(SYM_ITEM_MGR_PTR[base_id]) if base_id in SYM_ITEM_MGR_PTR else 0
        except Exception as e:
            logger.info(f"[DEBUG SAVE] Read error: {e}")
            return True

        in_level = is_in_level(base_id)
        save_active = is_save_active(base_id)
        logger.info(f"[DEBUG SAVE] mCurrGameSectionID = {section} (OnePlayer={SECTION_ONE_PLAYER})")
        logger.info(f"[DEBUG SAVE] mNextOnePlayerSectionID = {subsection} "
                    f"(NewPikiGame={ONEPLAYER_NEW_PIKI_GAME}, MapSelect={ONEPLAYER_MAP_SELECT}, "
                    f"CardSelect={ONEPLAYER_CARD_SELECT})")
        logger.info(f"[DEBUG SAVE] DAY_NUMBER = {day} | sentinel = 0x{sentinel:08X} "
                    f"| itemMgr = 0x{item_mgr:08X}")
        logger.info(f"[DEBUG SAVE] In a level: {'YES' if in_level else 'NO'} "
                    f"(ship parts + squad Pikmin)")
        logger.info(f"[DEBUG SAVE] Game active: {'YES' if save_active else 'NO'} "
                    f"— AP sync {'active' if save_active else 'paused'} "
                    f"(item reception + areas)")
        return True

    def _cmd_debugdump(self) -> bool:
        """Dump every debug info at once, to attach when reporting a bug."""
        ctx = self.ctx
        log = logger.info

        log("========== PIKMIN AP DEBUG DUMP ==========")
        log("Copy this whole block when reporting a bug.")
        log("------------------------------------------")

        # --- Client / AP state -------------------------------------------
        log(f"[DUMP] Pikmin apworld version: {APWORLD_VERSION}")
        log(f"[DUMP] AP world: Pikmin | client connected: {ctx.server is not None}")
        log(f"[DUMP] Slot: {getattr(ctx, 'auth', None)} | seed: {getattr(ctx, 'seed_name', None)}")
        slot_data = getattr(ctx, "slot_data", {}) or {}
        log(f"[DUMP] Hint mode: {slot_data.get('ship_part_hint_mode', 0)} | "
            f"day cycle mode: {slot_data.get('day_cycle_mode', 0)} | "
            f"game_id_suffix: {slot_data.get('game_id_suffix', '')!r}")
        log(f"[DUMP] Detected language: {getattr(ctx, 'detected_language', 'en')}")
        dl_mode = {0: "off", 1: "classic", 2: "pikmin", 3: "both"}.get(getattr(ctx, "death_link_mode", 0), "?")
        log(f"[DUMP] DeathLink: {dl_mode} | pikmin death amount: "
            f"{getattr(ctx, 'pikmin_death_amount', 0)} | TrapLink: "
            f"{getattr(ctx, 'trap_link_enabled', False)} | tags: {sorted(getattr(ctx, 'tags', []))}")
        log(f"[DUMP] Dolphin status: {getattr(ctx, 'dolphin_status_text', '?')}")
        log(f"[DUMP] Items received: {len(getattr(ctx, 'items_received', []))} | "
            f"locations checked: {len(getattr(ctx, 'checked_locations', []))} | "
            f"missing: {len(getattr(ctx, 'missing_locations', []))}")
        applied = _named_counts(getattr(ctx, "pikmin_items_applied", {}))
        if applied:
            log("[DUMP] Pikmin bonus applied:")
            for name, n in applied.items():
                log(f"[DUMP]   {name}: {n}")
        else:
            log("[DUMP] Pikmin bonus applied: (none)")
        traps = getattr(ctx, "traps_applied", {})
        trap_named = {_TRAP_KIND_TO_NAME.get(_TRAP_ID_TO_KIND.get(k, ""), f"#{k}"): v
                      for k, v in traps.items()}
        log(f"[DUMP] Traps applied: {trap_named or '(none)'} | "
            f"pending TrapLink: {getattr(ctx, 'pending_trap_links', [])}")
        log(f"[DUMP] Scouted locations: {len(getattr(ctx, 'scouted_locations', {}))} | "
            f"server hints: {len(getattr(ctx, 'server_hints', {}))}")

        if slot_data.get("hints"):
            log(f"[DUMP] Hints in slot_data: {len(slot_data['hints'])}")
            for part_name, hint_data in slot_data["hints"].items():
                log(f"[DUMP]   {part_name}: {hint_data.get('Item', '?')} "
                    f"@ {hint_data.get('Location', '?')}")

        # --- Live memory diagnostics (read-only) -------------------------
        log("------------------------------------------")
        if not dme.is_hooked():
            log("[DUMP] Dolphin not connected — no live memory dump.")
        else:
            # Reuse the read-only debug commands (none of them toggle state).
            self._cmd_debugsave()
            self._cmd_debuglanguage()
            self._cmd_debugtext()
            self._cmd_debugparts()

        log("========== END OF DEBUG DUMP ==========")
        return True

    def _cmd_debugonion(self) -> bool:
        """Show the state of the onions and their light beam (use in-game)."""
        if not dme.is_hooked():
            logger.info("[DEBUG ONION] Dolphin not connected.")
            return True
        try:
            raw = dme.read_bytes(0x80000000, 6)
        except Exception as e:
            logger.info(f"[DEBUG ONION] Could not read Game ID: {e}")
            return True
        game = BASE_ID_BY_PATCHED_PREFIX.get(raw[:3], raw)
        ctx = self.ctx

        def f32(a):
            return struct.unpack(">f", dme.read_bytes(a, 4))[0]

        def u32(a):
            return struct.unpack(">I", dme.read_bytes(a, 4))[0]

        try:
            ps = u32(SYM_PLAYER_STATE_PTR[game])
            cf = dme.read_byte(ps + PLAYERSTATE_OFFSETS["mContainerFlag"])
            df = dme.read_byte(ps + PLAYERSTATE_OFFSETS["mDisplayPikiFlag"])
            logger.info(f"[DEBUG ONION] mContainerFlag=0x{cf:02X} mDisplayPikiFlag=0x{df:02X} "
                        f"in_level={is_in_level(game)} day_active={is_day_active(game)} "
                        f"cone_ok={sorted(getattr(ctx, '_cone_ok', set()))} "
                        f"skip_events={sorted((getattr(ctx, 'slot_data', {}) or {}).get('skip_events', []))}")
            onions = find_onion_containers(game)
            if not onions:
                logger.info("[DEBUG ONION] No onion found in this area.")
            for color, g in onions.items():
                eff = u32(g + GOAL_SPOT_MODEL_EFF)
                line = (f"[DEBUG ONION] {color} @0x{g:08X} closing={dme.read_byte(g + GOAL_IS_CLOSING)} "
                        f"coneEmit={dme.read_byte(g + GOAL_IS_CONE_EMIT)} timer={f32(g + GOAL_CONE_TIMER):.2f} "
                        f"full=({f32(g + GOAL_CONE_FULL_SCALE):.2f},{f32(g + GOAL_CONE_FULL_SCALE + 4):.2f},"
                        f"{f32(g + GOAL_CONE_FULL_SCALE + 8):.2f}) spotEff=0x{eff:08X}")
                if _RAM_MIN <= eff < _RAM_MAX:
                    sc = struct.unpack(">fff", dme.read_bytes(eff + EFFSHPINST_SCALE, 12))
                    tr = struct.unpack(">fff", dme.read_bytes(eff + EFFSHPINST_SCALE + 24, 12))
                    line += (f" scale=({sc[0]:.2f},{sc[1]:.2f},{sc[2]:.2f}) "
                             f"pos=({tr[0]:.0f},{tr[1]:.0f},{tr[2]:.0f}) "
                             f"visible={dme.read_byte(eff + 0x42)}")
                gpos = struct.unpack(">fff", dme.read_bytes(g + 0x41C, 12))
                line += f" onionPos=({gpos[0]:.0f},{gpos[1]:.0f},{gpos[2]:.0f})"
                logger.info(line)
        except Exception as e:
            logger.info(f"[DEBUG ONION] Error: {e!r}")
        return True

    def _cmd_debugparts(self) -> bool:
        """Show the state of ship part pellets and radar icons (use in-game)."""
        if not dme.is_hooked():
            logger.info("[DEBUG PARTS] Dolphin not connected.")
            return True
        try:
            raw = dme.read_bytes(0x80000000, 6)
        except Exception as e:
            logger.info(f"[DEBUG PARTS] Could not read Game ID: {e}")
            return True
        game = BASE_ID_BY_PATCHED_PREFIX.get(raw[:3], raw)
        ctx = self.ctx
        checked = getattr(ctx, "checked_locations", set()) or set()
        ap_to_name = {d.ap_id: n for n, d in ALL_PARTS.items()}
        P = PELLET_CHAIN
        R = RADAR_CHAIN

        def u32(addr):
            try:
                v = int.from_bytes(dme.read_bytes(addr, 4), "big")
            except Exception:
                return 0
            return v if _RAM_MIN <= v < _RAM_MAX else 0

        def obj_info(obj):
            """Return (objType, model_id, ap_id, name, is_alive) for an object, or None."""
            try:
                obj_type = int.from_bytes(
                    dme.read_bytes(obj + ONION_CHAIN["CREATURE_OBJTYPE"], 4), "big", signed=True
                )
            except Exception:
                return None
            model_id = None
            ap_id = None
            if obj_type == OBJTYPE_PELLET:
                config = u32(obj + P["PELLET_CONFIG"])
                if config:
                    try:
                        model_id = dme.read_bytes(config + P["PELLETCONFIG_MODELID"], 4)
                    except Exception:
                        model_id = None
                ap_id = _MODELID_TO_AP_ID.get(model_id) if model_id else None
            try:
                alive = dme.read_byte(obj + P["PELLET_ISALIVE"])
            except Exception:
                alive = -1
            return obj_type, model_id, ap_id, ap_to_name.get(ap_id), alive

        logger.info("========== PIKMIN PARTS DUMP ==========")
        logger.info(f"[DEBUG PARTS] Game: {game!r} | parts checked on server: "
                    f"{sorted(ap_to_name[a] for a in checked if a in ap_to_name)}")

        # --- pelletMgr: ALL slots (even mEntryStatus != 0), to spot
        #     a pellet held/swallowed by a creature.
        mgr = u32(SYM_PELLET_MGR_PTR.get(game, 0)) if game in SYM_PELLET_MGR_PTR else 0
        if not mgr:
            logger.info("[DEBUG PARTS] pelletMgr not found.")
        else:
            obj_list = u32(mgr + P["MONO_OBJECTLIST"])
            entry_status = u32(mgr + P["MONO_ENTRYSTATUS"])
            try:
                max_elems = int.from_bytes(dme.read_bytes(mgr + P["MONO_MAXELEMENTS"], 4), "big", signed=True)
            except Exception:
                max_elems = 0
            logger.info(f"[DEBUG PARTS] pelletMgr @0x{mgr:08X} maxElems={max_elems}")
            shown = 0
            for i in range(max(0, min(max_elems, 4096))):
                obj = u32(obj_list + i * 4)
                if not obj:
                    continue
                info = obj_info(obj)
                if not info or info[0] != OBJTYPE_PELLET or info[2] is None:
                    continue  # only ship part pellets (known model)
                obj_type, model_id, ap_id, name, alive = info
                try:
                    status = int.from_bytes(dme.read_bytes(entry_status + i * 4, 4), "big", signed=True)
                except Exception:
                    status = "?"
                shown += 1
                logger.info(f"[DEBUG PARTS] pellet slot={i} @0x{obj:08X} status={status} "
                            f"model={model_id!r} ap={ap_id} ({name}) alive={alive} "
                            f"checked={'YES' if ap_id in checked else 'no'}")
            if not shown:
                logger.info("[DEBUG PARTS] No ship part pellet in pelletMgr.")

        # --- radar: icons actually drawn on the map.
        radar = u32(SYM_RADAR_INFO_PTR.get(game, 0)) if game in SYM_RADAR_INFO_PTR else 0
        if not radar:
            logger.info("[DEBUG PARTS] radarInfo not found.")
        else:
            node = u32(radar + R["ALIVE_CHILD"])
            n = 0
            while node and n < 128:
                n += 1
                part = u32(node + R["NODE_PART"])
                nxt = u32(node + R["NODE_NEXT"])
                if part:
                    info = obj_info(part)
                    if info:
                        obj_type, model_id, ap_id, name, alive = info
                        logger.info(f"[DEBUG PARTS] radar node @0x{node:08X} part=0x{part:08X} "
                                    f"objType={obj_type} model={model_id!r} ap={ap_id} ({name}) "
                                    f"alive={alive} checked={'YES' if ap_id in checked else 'no'}")
                        # The node points to a CREATURE (e.g. Snagret) that HOLDS a part:
                        # scan its object for a known part fourCC or a pointer to a
                        # part Pellet/PelletConfig to find how it references the part.
                        if obj_type != OBJTYPE_PELLET:
                            known = set(_MODELID_TO_AP_ID.keys())
                            found = []
                            try:
                                blob = dme.read_bytes(part, 0x600)
                            except Exception:
                                blob = b""
                            for off in range(0, len(blob) - 3, 4):
                                w = blob[off:off + 4]
                                if w in known:
                                    found.append(f"+0x{off:X}=fourCC {w!r}({_MODELID_TO_AP_ID[w]})")
                                    continue
                                p = int.from_bytes(w, "big")
                                if _RAM_MIN <= p < _RAM_MAX:
                                    try:
                                        ot = int.from_bytes(dme.read_bytes(p + ONION_CHAIN["CREATURE_OBJTYPE"], 4), "big", signed=True)
                                    except Exception:
                                        ot = None
                                    if ot == OBJTYPE_PELLET:
                                        cfg = u32(p + P["PELLET_CONFIG"])
                                        m = None
                                        if cfg:
                                            try:
                                                m = dme.read_bytes(cfg + P["PELLETCONFIG_MODELID"], 4)
                                            except Exception:
                                                m = None
                                        if m in known:
                                            found.append(f"+0x{off:X}=Pellet*0x{p:08X}(model {m!r} ap={_MODELID_TO_AP_ID[m]})")
                                    else:
                                        try:
                                            m = dme.read_bytes(p + P["PELLETCONFIG_MODELID"], 4)
                                        except Exception:
                                            m = None
                                        if m in known:
                                            found.append(f"+0x{off:X}=Config*0x{p:08X}(model {m!r} ap={_MODELID_TO_AP_ID[m]})")
                            for f in found:
                                logger.info(f"[DEBUG PARTS]   creature-part ref {f}")
                            if not found:
                                logger.info("[DEBUG PARTS]   creature-part ref: no part fourCC/pellet found in +0..0x600")
                node = nxt
            if n == 0:
                logger.info("[DEBUG PARTS] radar mAlivePartsList empty.")

        logger.info("========== END PARTS DUMP ==========")
        return True


# --- Client shutdown ------------------------------------------------------

# Max delay (s) between a close request (window X or /exit) and process exit.
EXIT_WATCHDOG_SECONDS = 6
_exit_watchdog_file = None


_exit_watchdog_armed = False


def _arm_exit_watchdog() -> None:
    """Guarantee the process terminates after a close request.

    faulthandler.dump_traceback_later() arms a C-level timer that is independent
    of the GIL and the asyncio loop: if not cancelled in time, it writes the
    stack of ALL threads to the log and kills the process. It works even if the
    main thread is stuck in a C call (dolphin_memory_engine, Kivy/SDL, thread join...).
    """
    global _exit_watchdog_file, _exit_watchdog_armed
    if _exit_watchdog_armed:
        return
    _exit_watchdog_armed = True
    stream = None
    for h in logging.getLogger().handlers:
        if isinstance(h, logging.FileHandler) and getattr(h, "stream", None):
            stream = h.stream
            break
    try:
        if stream is None:
            _exit_watchdog_file = open(Utils.user_path("logs", "PikminClient_exit_freeze.txt"), "a")
            stream = _exit_watchdog_file
        stream.write(f"\n[Pikmin] Exit requested: if the client has not closed within "
                     f"{EXIT_WATCHDOG_SECONDS}s, thread stacks are dumped below "
                     f"and the process is force-terminated.\n")
        stream.flush()
        faulthandler.dump_traceback_later(EXIT_WATCHDOG_SECONDS, exit=True, file=stream)
    except Exception as e:
        logger.debug(f"Exit watchdog not armed: {e}")


class _P1ExitEvent(asyncio.Event):
    """exit_event that arms the exit watchdog as soon as it is set
    (window close via kvui.on_stop, /exit, or anything else)."""

    def set(self) -> None:
        if not self.is_set():
            _arm_exit_watchdog()
        super().set()


class P1Context(SuperContext):
    command_processor = P1CommandProcessor
    game: str = "Pikmin"
    items_handling: int = 0b111
    # UT adds the "Tracker" tag (tracker-only connection); here we actually play,
    # so keep the tags of a normal game client.
    tags = {"AP"}

    def __init__(self, server_address: Optional[str], password: Optional[str]) -> None:
        super().__init__(server_address, password)
        self.items_handling = 0b111  # UT redefines it in its __init__
        # Game detected in Dolphin / pending connection / slot name read from the ISO.
        self.game_detected: bool = False
        self._pending_connect: Optional[str] = None
        self.iso_slot_name: str = ""
        self._detected_game_id: Optional[bytes] = None
        # exit_event that arms the exit watchdog.
        self.exit_event = _P1ExitEvent()
        self.dolphin_status_text = "Disconnected"
        self._override_warned = False

        # Track Pikmin counts for location checking
        self.pikmin_counts = {"red": 0, "yellow": 0, "blue": 0}
        self.pikmin_location_ids = {}
        self.last_red_count = 0
        self.last_yellow_count = 0
        self.last_blue_count = 0

        # Track how many Pikmin bonus items have already been applied
        self.pikmin_items_applied: dict[int, int] = {}
        # Custom Save: applied Pikmin bonuses, per game save
        # (key = save file checksum, hex). See track_game_save().
        self.game_saves: dict[str, dict] = {}
        self._save_prev_sub: Optional[int] = None
        self._save_crc: Optional[int] = None
        self._pending_save_load: Optional[tuple] = None
        # Pikmin bonuses received outside a day, to be counted as "sprouts" at the
        # start of the next day (color -> count).
        self._pending_born: dict[str, int] = {"red": 0, "yellow": 0, "blue": 0}
        # Abandoned onions / number of cone corrections, per day.
        self._cone_ok: set = set()
        self._cone_tries: dict = {}
        self._cone_free_since: Optional[float] = None
        self._client_kill_reason: Optional[str] = None
        self._olimar_bond_last: Optional[int] = None     # bornPikis reference
        # Day start detection for safety check
        self.last_hour: int = -1
        # Debug mode toggles (via /debughint, /debugdays, /debugpbonus)
        self.debug_mode: bool = False  # kept for legacy internal checks
        self.debug_hint: bool = False
        self.debug_days: bool = False
        self.debug_pbonus: bool = False
        self.debug_trap: bool = False
        # Tracks whether the dynamic onion sentinel was zero last tick.
        # Used to detect the 0->nonzero transition = onion freshly loaded for new day.
        self._onion_dyn_was_zero: bool = True
        self._dyn_base_red: int | None = None
        self._dyn_base_yellow: int | None = None
        self._dyn_base_blue: int | None = None
        # Ship part hint tracking
        self.last_hint_shown: str = ""
        # Raw bytes of the hint we wrote, so we can re-apply if the game overwrites it
        self.last_hint_bytes: bytes = b""
        # Throttle for day cycle debug logs (timestamp of last log)
        self._last_day_debug_log: float = 0.0
        # Scouted locations: loc_id -> {"item_name": str, "player": int}
        self.scouted_locations: dict[int, dict] = {}
        # Flag to trigger location scout after connection is fully established
        self.needs_location_scout: bool = False
        # Track scout state for retry logic
        self.scout_sent: bool = False
        self.scout_sent_time: float = 0.0
        self.scout_received: bool = False
        # Track which location hints have been created on the server
        self.created_hints: set[int] = set()
        # Super Radar: cache of ALL scouted locations (not just own)
        self.all_locations_scouted: dict[int, dict] = {}
        # Super Radar: track that we've requested all-locations scout
        self.super_radar_requested: bool = False
        self.super_radar_hints_created: bool = False
        # Super Radar: store hints received from server
        self.server_hints: dict[int, dict] = {}
        # Slot data received from server on connection
        self.slot_data: dict = {}
        # Both mode: toggle between item/radar display
        self.hint_both_toggle: bool = False
        self.hint_both_last_toggle: float = 0.0
        # Detected game language (set during DAY_NUMBER == 0 phase)
        self.detected_language: str = "en"  # default English
        # Was a save loaded on the previous tick? Used to log only transitions
        # (load / return to title), not every tick.
        self._save_was_loaded: bool = False

        # QOL Disable Pikmin Trip, 'item' mode: the RAM patch removing tripping is
        # applied only once, after the 'Trip Immunity' item is received.
        self._trip_ram_patched: bool = False
        # Trip Trap: remaining gameplay seconds (0 = inactive).
        self._trip_trap_remaining: float = 0.0
        self._trip_trap_last: float = 0.0

        # --- DeathLink / TrapLink ---
        # Configured from slot_data on connection.
        self.death_link_mode: int = 0        # 0=off, 1=classic, 2=pikmin, 3=both
        self.pikmin_death_amount: int = 10
        self.trap_link_enabled: bool = False
        # Conversion of unknown cross-game TrapLink traps: True = an unknown trap
        # (from another game) is converted into a random Pikmin trap; False =
        # it is ignored. `trap_link_conversion_traps` restricts the pool of Pikmin
        # traps usable for conversion (empty = all).
        self.trap_link_conversion: bool = True
        self.trap_link_conversion_traps: list = []
        # Send-side detection.
        self._orima_was_dead: bool = False   # dead state on the previous tick (rising edge)
        # deadPikis is already reset by the game each day; track the previous
        # tick's value to detect the reset (new day) and restart DeathLink counting.
        self._dead_pikis_last: Optional[int] = None
        self._dead_pikis_sent: int = 0       # number of DeathLinks already sent this day
        # Olimar/Pikmin bond: HP lost per dead Pikmin.
        self.pikmin_bond: bool = False
        self.pikmin_bond_damage: float = 5.0
        self._bond_dead_last: Optional[int] = None  # deadPikis reference (per day)
        # Receive side: a received DeathLink kills Olimar on the next in-game tick.
        self.pending_kill: bool = False
        # Prevents echo: an Olimar death caused by a received DeathLink must not
        # emit another DeathLink (classic mode).
        self._suppress_orima_send: bool = False
        # Timestamps of our own sent DeathLinks, to filter our deaths coming back
        # from the server (CommonClient's filter only keeps the last one).
        self._sent_death_times: set = set()
        # Safety: only one DeathLink event (send OR receive) per day.
        # Locked after the first event, re-armed at the start of the next day
        # (rising edge of "in a level"). Prevents any residual cascade.
        self._deathlink_locked_this_day: bool = False
        self._in_level_prev: bool = False
        # Both mode: pending Olimar self-kill if it could not be resolved at send time.
        self._pending_self_kill: bool = False
        # Traps received via TrapLink (transient), waiting to be applied in game.
        self.pending_trap_links: list = []
        self.pending_trap_link_sources: list = []  # parallel to pending_trap_links
        self._trap_source: Optional[str] = None     # player who originated the current trap
        # Traps received as AP items and already applied: {item_id: count}.
        self.traps_applied: dict[int, int] = {}
        # After an End Day Trap: suspend ALL trap application until the start of
        # the next day (chained End Day Traps would send the game to the main menu
        # without saving).
        self._traps_suspended_until_next_day: bool = False
        # Grace period at day start: skip a few active gameplay ticks before
        # applying a trap, so none is wasted right after landing (Olimar not yet
        # fully operational).
        self._trap_grace_ticks: int = 0
        self._trap_free_since: Optional[float] = None
        self._dl_free_since: Optional[float] = None  
        self._bond_kill_pending: bool = False
        self.death_cause_ring: Optional[int] = None   
        self.tracker_stage_name: Optional[str] = None 
        self.visited_stage_names: Optional[set] = None
        # True while a screen (pause, map, text...) covers gameplay; used to
        # re-arm the grace period when the menu closes.
        self._trap_overlay_was_active: bool = False
        # Transition tracking to reset the DeathLink state per day.
        self._save_was_loaded_prev_death: bool = False

    def _save_key(self) -> str:
        slot_data = getattr(self, "slot_data", {}) or {}
        suffix = slot_data.get("game_id_suffix", "")
        if suffix:
            return f"applied_{self.auth}_P1P{suffix}"
        seed = getattr(self, "seed_name", None) or "unknown"
        return f"applied_{self.auth}_{seed}"

    def load_applied(self) -> None:
        key = self._save_key()
        if self.debug_hint:
            logger.info(f"[DEBUG] load_applied key: {key}")
        try:
            data = Utils.persistent_load().get("pikmin", {}).get(self._save_key(), {})
            self.pikmin_items_applied = {int(k): v for k, v in data.items()}
            if self.debug_hint:
                logger.info(f"[DEBUG] Loaded {len(self.pikmin_items_applied)} applied Pikmin items")
        except Exception as e:
            logger.debug(f"Could not load applied items: {e}")
        # "Already applied" state of each game save.
        try:
            self.game_saves = dict(Utils.persistent_load().get("pikmin_saves", {}).get(key, {}) or {})
        except Exception as e:
            self.game_saves = {}
            logger.debug(f"Could not load game saves: {e}")
        # Already-applied traps (so a trap is not replayed on restart).
        try:
            tdata = Utils.persistent_load().get("pikmin_traps", {}).get(self._save_key(), {})
            self.traps_applied = {int(k): v for k, v in tdata.items()}
        except Exception as e:
            logger.debug(f"Could not load applied traps: {e}")

    def save_applied(self) -> None:
        # After a disconnect, reset_server_state() sets self.auth to None:
        # writing then would create a stray "applied_None_..." entry.
        if not self.auth:
            return
        try:
            Utils.persistent_store("pikmin", self._save_key(),
                                   {str(k): v for k, v in self.pikmin_items_applied.items()})
        except Exception as e:
            logger.debug(f"Could not save applied items: {e}")
        try:
            Utils.persistent_store("pikmin_traps", self._save_key(),
                                   {str(k): v for k, v in self.traps_applied.items()})
        except Exception as e:
            logger.debug(f"Could not save applied traps: {e}")

    def store_game_saves(self) -> None:
        """Persist per-game-save state (capped at MAX_TRACKED_SAVES)."""
        if not self.auth:
            return
        while len(self.game_saves) > MAX_TRACKED_SAVES:
            self.game_saves.pop(next(iter(self.game_saves)))
        try:
            Utils.persistent_store("pikmin_saves", self._save_key(), dict(self.game_saves))
        except Exception as e:
            logger.debug(f"Could not store game saves: {e}")

    def reset_server_state(self) -> None:
        """Start from a clean state on every disconnect.

        Otherwise a reconnection would reuse the previous session's slot_data,
        scouts and hints, and the LocationScouts retry loop would keep sending
        on a closed socket.
        """
        super().reset_server_state()
        self.slot_data = {}
        self.scouted_locations = {}
        self.all_locations_scouted = {}
        self.server_hints = {}
        self.created_hints = set()
        self.needs_location_scout = False
        self.scout_sent = False
        self.scout_received = False
        self.super_radar_requested = False
        self.super_radar_hints_created = False
        self.last_hint_shown = ""
        self.last_hint_bytes = b""

    def make_gui(self) -> "type[kvui.GameManager]":
        # Build the Pikmin UI on top of the parent's (Universal Tracker UI with its
        # tab if installed, otherwise the standard UI).
        from .P1UI import build_p1_ui
        return build_p1_ui(super().make_gui())

    # --- Connect only once the game is detected ---------------------------------
    async def connect(self, address: Optional[str] = None) -> None:
        """Connect only once Pikmin (patched ISO) is detected in Dolphin;
        otherwise the address is kept pending and dolphin_loop retries the
        connection as soon as the game is detected."""
        if not self.game_detected:
            self._pending_connect = address if address is not None else (self.server_address or "")
            lang = getattr(self, "detected_language", "en")
            logger.info("[Pikmin] " + WAIT_GAME_MSG.get(lang, WAIT_GAME_MSG["en"]))
            return
        await super().connect(address)

    async def server_auth(self, password_requested: bool = False) -> None:
        # Standard Archipelago client pattern: only delegate to the parent for
        # password entry, otherwise there is nothing to do.
        if password_requested and not self.password:
            # Call CommonContext directly: UT's version chains get_username/send_connect
            # itself, which would connect twice.
            await CommonContext.server_auth(self, password_requested)
        # Slot name read from the patched ISO (otherwise manual entry).
        if not self.auth and not self.username and self.iso_slot_name:
            self.username = self.iso_slot_name
            lang = getattr(self, "detected_language", "en")
            msg = SLOT_FROM_ISO_MSG.get(lang, SLOT_FROM_ISO_MSG["en"])
            logger.info("[Pikmin] " + msg.format(name=self.iso_slot_name))
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict) -> None:
        if self.debug_hint:
            logger.info(f"[DEBUG] on_package cmd={cmd}")
        super().on_package(cmd, args)
        if cmd == "RoomInfo":
            # The real seed_name is only present in RoomInfo. Store it here, after
            # CommonClient's reconnection guard (which runs before on_package),
            # so reconnection compares seed == seed and debug dumps show the right seed.
            self.seed_name = args.get("seed_name") or self.seed_name
        elif cmd == "Retrieved":
            # Set of already visited zones (dict used as a set).
            key = AP_VISITED_STAGE_NAMES_KEY_FORMAT % self.slot if self.slot is not None else None
            keys = args.get("keys", {})
            if key and key in keys:
                self.visited_stage_names = set((keys[key] or {}).keys())
        elif cmd == "Connected":
            self.slot_data = args.get("slot_data", {})
            if self.debug_hint:
                logger.info(f"[DEBUG] slot_data received: {self.slot_data}")
            self.pikmin_items_applied = {}  # reset before loading with correct key
            self.traps_applied = {}
            self.pikmin_dyn_pending = {"red": 0, "yellow": 0, "blue": 0}
            self.load_applied()
            self.needs_location_scout = True
            # Register for hints notifications
            self.stored_data_notification_keys.add(f"_read_hints_{self.team}_{self.slot}")
            # Already visited zones (PopTracker), like the TWW client.
            async_start(self.send_msgs([{"cmd": "Get", "keys": [AP_VISITED_STAGE_NAMES_KEY_FORMAT % self.slot]}]))
            self.tracker_stage_name = None  # resend the current zone after (re)connection

            # --- DeathLink / TrapLink: configure tags from slot_data ---
            self.death_link_mode = int(self.slot_data.get("death_link", 0))
            self.pikmin_death_amount = max(1, int(self.slot_data.get("pikmin_death_amount", 10)))
            self.trap_link_enabled = bool(self.slot_data.get("trap_link", 0))
            # Conversion of unknown cross-game traps (default: enabled).
            self.trap_link_conversion = bool(self.slot_data.get("trap_link_conversion", 1))
            # Pool of traps allowed for conversion: keep only valid Pikmin trap
            # names; empty -> all.
            allowed = self.slot_data.get("trap_link_conversion_traps", []) or []
            self.trap_link_conversion_traps = [n for n in allowed if n in TRAP_KINDS]
            self._orima_was_dead = False
            self._dead_pikis_baseline = None
            self._dead_pikis_sent = 0
            self.pending_kill = False
            # Olimar/Pikmin bond
            self.pikmin_bond = bool(self.slot_data.get("pikmin_bond", 0))
            self.pikmin_bond_damage = float(max(1, int(self.slot_data.get("pikmin_bond_damage", 5))))
            self._bond_dead_last = None
            _lang = getattr(self, "detected_language", "en")
            if self.pikmin_bond:
                _m = BOND_ACTIVE_MSG.get(_lang, BOND_ACTIVE_MSG["en"])
                logger.info("[Pikmin] " + _m.format(dmg=f"{self.pikmin_bond_damage:g}"))
            tags = set(self.tags)
            if self.death_link_mode != 0:
                tags.add("DeathLink")
            if self.trap_link_enabled:
                tags.add("TrapLink")
            if tags != set(self.tags):
                self.tags = tags
                async_start(self.send_msgs([{"cmd": "ConnectUpdate", "tags": list(self.tags)}]))
            if self.death_link_mode != 0:
                _dl = {1: "classic", 2: "pikmin", 3: "both"}.get(self.death_link_mode, "?")
                _m = DEATHLINK_ACTIVE_MSG.get(_lang, DEATHLINK_ACTIVE_MSG["en"])
                logger.info("[Pikmin] " + _m.format(mode=_dl))
            if self.trap_link_enabled:
                logger.info("[Pikmin] " + TRAPLINK_ACTIVE_MSG.get(_lang, TRAPLINK_ACTIVE_MSG["en"]))
        elif cmd == "LocationInfo":
            count = len(args.get("locations", []))
            if self.debug_hint:
                logger.info(f"[DEBUG] Received LocationInfo with {count} locations")
            for item in args["locations"]:
                loc_id = item.location
                try:
                    item_name = self.item_names.lookup_in_slot(item.item, item.player)
                except Exception:
                    item_name = str(item.item)
                entry = {
                    "item_name": item_name,
                    "player":    item.player,
                    "flags":     item.flags if hasattr(item, "flags") else 0,
                }
                self.scouted_locations[loc_id] = entry
                self.all_locations_scouted[loc_id] = entry
            self.scout_received = True
            if self.debug_hint:
                logger.info(f"[DEBUG] Scouted {len(self.scouted_locations)} locations total")

        elif cmd == "SetReply":
            if args.get("key") == f"_read_hints_{self.team}_{self.slot}":
                hints = args.get("value", [])
                if self.debug_hint:
                    logger.info(f"[DEBUG] Received hints via SetReply: {len(hints)} hints")
                for hint in hints:
                    loc_id = hint.get("location")
                    if loc_id:
                        self.server_hints[loc_id] = hint
                if self.debug_hint:
                    logger.info(f"[DEBUG] Server hints total: {len(self.server_hints)}")

        elif cmd == "ReceivedHints":
            if self.debug_hint:
                logger.info(f"[DEBUG] ReceivedHints: {len(args.get('hints', []))} hints")
            for hint in args.get("hints", []):
                loc_id = hint.get("location")
                if loc_id:
                    self.server_hints[loc_id] = hint
            if self.debug_hint:
                logger.info(f"[DEBUG] Server hints total: {len(self.server_hints)}")

        elif cmd == "Bounced":
            # TrapLink: another player received a trap and broadcasts it. Apply the
            # same trap here. (DeathLink is already handled by CommonClient.)
            tags = args.get("tags", [])
            if "TrapLink" in tags:
                data = args.get("data", {}) or {}
                source = data.get("source")
                mine = self.player_names.get(self.slot)
                trap_name = data.get("trap_name") or data.get("cause") or ""
                if self.debug_trap:
                    logger.info(f"[TrapLink] Bounce received: trap='{trap_name}' source={source} "
                                f"(me={mine}, enabled={self.trap_link_enabled}).")
                if not self.trap_link_enabled:
                    pass  # ignore (logged if debug)
                elif source == mine:
                    if self.debug_trap:
                        logger.info("[TrapLink] Ignored: this is our own broadcast.")
                elif trap_name not in TRAP_KINDS or (trap_name == "Trip Trap" and _trip_mode(self) == 1):
                    # TrapLink is CROSS-GAME: the name comes from the sending game. If
                    # unknown (e.g. a Hollow Knight trap), either convert it to a random
                    # Pikmin trap (TrapLink convention) or ignore it, depending on the
                    # `trap_link_conversion` option.
                    if not self.trap_link_conversion:
                        if self.debug_trap:
                            logger.info(f"[TrapLink] Unknown trap '{trap_name}' ignored "
                                        "(conversion disabled).")
                    else:
                        # Pool restricted by the option (empty -> all Pikmin traps).
                        pool = self.trap_link_conversion_traps or [
                            n for n in TRAP_KINDS
                            # No Trip Trap if tripping is removed from the game.
                            if not (n == "Trip Trap" and _trip_mode(self) == 1)
                        ]
                        converted = random.choice(pool)
                        if self.debug_trap:
                            logger.info(f"[TrapLink] Unknown name -> random Pikmin trap: "
                                        f"'{converted}' (pool={pool}).")
                        self.queue_trap_link(converted, source)
                        if self.debug_trap:
                            logger.info(f"[TrapLink] Trap '{converted}' queued for application.")
                else:
                    # Already known name (Pikmin trap): apply as-is, no conversion.
                    self.queue_trap_link(trap_name, source)
                    if self.debug_trap:
                        logger.info(f"[TrapLink] Trap '{trap_name}' queued for application.")

    async def send_death(self, death_text: str = "") -> None:
        """Send a DeathLink and remember its timestamp.

        CommonClient's anti-echo filter only keeps the LAST sent timestamp
        (last_death_link). If several deaths are sent in quick succession, the
        earlier ones come back from the server and are mistaken for received
        deaths (retrigger loop, especially in both mode). So we remember ALL our
        timestamps to filter our own deaths in on_deathlink.
        """
        await super().send_death(death_text)
        self._sent_death_times.add(self.last_death_link)
        # Archipelago's generic message ("Sending death to your friends...") does
        # not show the cause sent to other players: show it too.
        if death_text and self.server and self.server.socket:
            logger.info(f"DeathLink: {death_text}")
        # Bound memory (old timestamps will not come back).
        if len(self._sent_death_times) > 64:
            self._sent_death_times = set(sorted(self._sent_death_times)[-32:])

    def on_deathlink(self, data: dict) -> None:
        """Received DeathLink: schedule Olimar's death, ignoring our own deaths."""
        if data.get("time") in self._sent_death_times:
            # One of our own deaths echoed back by the server: ignore.
            self.last_death_link = max(data["time"], self.last_death_link)
            return
        super().on_deathlink(data)
        self.pending_kill = True

    def queue_trap_link(self, trap_name: str, source: Optional[str] = None) -> None:
        """Queue a trap received via TrapLink for application (overridable)."""
        self.pending_trap_links.append(trap_name)
        self.pending_trap_link_sources.append(source)  # source player

    async def send_trap_link(self, trap_name: str) -> None:
        """Broadcast the trap we just suffered to other TrapLink players."""
        if not self.trap_link_enabled:
            if self.debug_trap:
                logger.info("[TrapLink] Send skipped: TrapLink disabled.")
            return
        if not (self.server and self.server.socket):
            if self.debug_trap:
                logger.info("[TrapLink] Send skipped: not connected to the server.")
            return
        source = self.player_names.get(self.slot, "Pikmin")
        if self.debug_trap:
            logger.info(f"[TrapLink] Sending trap '{trap_name}' (source={source}, tags={sorted(self.tags)}).")
        await self.send_msgs([{
            "cmd": "Bounce",
            "tags": ["TrapLink"],
            "data": {
                "time": time.time(),
                "source": source,
                "trap_name": trap_name,
            },
        }])


COLOR_BY_INDEX = {0: "blue", 1: "red", 2: "yellow"}  # GlobalGameOptions.h


# --- PopTracker (automatic tab switching) --------------------------------------
#  - Bounce {"pikmin_stage_name": <zone>} on every zone change;
#  - server storage "pikmin_visited_stages_<slot>" = {zone: True} (visited zones).
AP_STAGE_NAME_BOUNCE_KEY = "pikmin_stage_name"
AP_VISITED_STAGE_NAMES_KEY_FORMAT = "pikmin_visited_stages_%i"
TRACKER_STAGE_NAMES = {0: "The Impact Site", 1: "The Forest of Hope", 2: "The Forest Navel",
                       3: "The Distant Spring", 4: "The Final Trial"}
TRACKER_WORLD_MAP = "World Map"
TRACKER_ONION_NAMES = {"red": "Red Onion", "yellow": "Yellow Onion", "blue": "Blue Onion"}
NAVISTATE_CONTAINER = 12  # onion menu open (include/NaviState.h)


def _open_onion_color(game: Game) -> Optional[str]:
    """Return the color of the onion whose menu is open, or None."""
    navi = _resolve_olimar(game)
    if navi is None:
        return None
    try:
        cont = _resolve_state_instance(navi, NAVISTATE_CONTAINER)
        cur = struct.unpack(">I", dme.read_bytes(navi + NAVI_CHAIN["NAVI_CURRSTATE"], 4))[0]
        if cont is None or cur != cont:
            return None
        goal = struct.unpack(">I", dme.read_bytes(navi + NAVI_CHAIN["NAVI_GOALITEM"], 4))[0]
        if not (_RAM_MIN <= goal < _RAM_MAX):
            return None
        colour = int.from_bytes(dme.read_bytes(goal + ONION_CHAIN["GOAL_COLOUR"], 2), "big")
        return COLOR_BY_INDEX.get(colour)
    except Exception:
        return None


def current_tracker_stage(game: Game) -> Optional[str]:
    """Return the PopTracker "zone" name (open onion, stage, world map), or None."""
    sub = _oneplayer_subsection(game)
    if sub == ONEPLAYER_MAP_SELECT:
        return TRACKER_WORLD_MAP
    if sub != ONEPLAYER_NEW_PIKI_GAME:
        return None
    color = _open_onion_color(game)
    if color:
        return TRACKER_ONION_NAMES[color]
    addr = SYM_GAMEFLOW.get(game, {}).get("CURRENT_STAGE_ID")
    if addr is None:
        return None
    try:
        return TRACKER_STAGE_NAMES.get(struct.unpack(">i", dme.read_bytes(addr, 4))[0])
    except Exception:
        return None


async def handle_tracker_stage(ctx: "P1Context", game: Game) -> None:
    """Tell PopTracker the current zone (Bounce) and the visited zones."""
    if not ctx.slot or not getattr(ctx, "auth", None):
        return
    name = current_tracker_stage(game)
    if not name or name == ctx.tracker_stage_name:
        return
    ctx.tracker_stage_name = name
    await ctx.send_msgs([{"cmd": "Bounce", "slots": [ctx.slot],
                          "data": {AP_STAGE_NAME_BOUNCE_KEY: name}}])
    visited = ctx.visited_stage_names
    if visited is not None and name not in visited:
        visited.add(name)
        await ctx.send_msgs([{"cmd": "Set", "key": AP_VISITED_STAGE_NAMES_KEY_FORMAT % ctx.slot,
                              "default": {}, "want_reply": False,
                              "operations": [{"operation": "update", "value": {name: True}}]}])


def find_onion_containers(game: Game) -> dict[str, int]:
    """Locate the live onions (GoalItem) by color.

    Mirrors `ItemMgr::getContainer()` from the decomp: follow a pointer chain and
    walk the linked list of creatures, filtering on mObjType == OBJTYPE_Goal.

        itemMgr -> mMeltingPotMgr -> mRootNode.mChild -> ... -> mNext
                -> mCreature (Creature*) -> GoalItem

    Returns {color: GoalItem address}. Empty dict if nothing is loaded
    (menu, transition), which is a normal state and not an error.
    """
    base_ptr = SYM_ITEM_MGR_PTR.get(game)
    if base_ptr is None:
        return {}

    C = ONION_CHAIN

    def deref(addr: int) -> int:
        """Read a 32-bit pointer and reject anything outside MEM1/MEM2."""
        try:
            val = int.from_bytes(dme.read_bytes(addr, 4), "big")
        except Exception:
            return 0
        # Only valid GameCube/Wii addresses, to avoid following garbage.
        if _RAM_MIN <= val < _RAM_MAX:
            return val
        return 0

    item_mgr = deref(base_ptr)
    if not item_mgr:
        return {}

    melting_pot = deref(item_mgr + C["ITEMMGR_MELTINGPOT"])
    if not melting_pot:
        return {}

    node = deref(melting_pot + C["MGR_ROOTNODE"] + C["NODE_CHILD"])

    found: dict[str, int] = {}
    seen: set[int] = set()

    # Safety guard: bounded linked-list walk, protects against cycles or
    # half-initialized memory during a load.
    for _ in range(4096):
        if not node or node in seen:
            break
        seen.add(node)

        creature = deref(node + C["NODE_CREATURE"])
        if creature:
            try:
                obj_type = int.from_bytes(
                    dme.read_bytes(creature + C["CREATURE_OBJTYPE"], 4), "big", signed=True
                )
            except Exception:
                obj_type = -1

            if obj_type == OBJTYPE_GOAL:
                try:
                    colour = int.from_bytes(
                        dme.read_bytes(creature + C["GOAL_COLOUR"], 2), "big"
                    )
                except Exception:
                    colour = -1
                name = COLOR_BY_INDEX.get(colour)
                if name and name not in found:
                    found[name] = creature

        if len(found) == 3:
            break

        node = deref(node + C["NODE_NEXT"])

    return found


# fourCC (model ID) -> part ap_id, to identify an in-game Pellet.
_MODELID_TO_AP_ID = {
    PART_MODEL_ID[name]: ALL_PARTS[name].ap_id
    for name in PART_MODEL_ID if name in ALL_PARTS
}

# ap_id -> stage, to rebuild the PlayerState counters.
_APID_TO_STAGE = {
    data.ap_id: AREA_STAGE_ID[data.area]
    for data in ALL_PARTS.values() if data.area in AREA_STAGE_ID
}
# ap_id -> ship effect bit (radar, jets).
_APID_TO_EFFECT = {
    ALL_PARTS[name].ap_id: bit
    for name, bit in SHIP_EFFECT_PARTS.items() if name in ALL_PARTS
}


def sync_playerstate_parts(ctx: P1Context, game: Game) -> None:
    """Reconcile the PlayerState part counters with the server-checked locations.

    Keeps abilities (radar, jets) and per-stage stars correct even for parts
    collected outside the game. Idempotent and never decreasing: only adds effect
    bits and raises counters to the max, never overwrites a higher in-game total.
    """
    ptr = SYM_PLAYER_STATE_PTR.get(game)
    if ptr is None:
        return
    try:
        ps = struct.unpack(">I", dme.read_bytes(ptr, 4))[0]
    except Exception:
        return
    if not (_RAM_MIN <= ps < _RAM_MAX):
        return
    O = PLAYERSTATE_OFFSETS

    checked = ctx.checked_locations
    ship_ids = {data.ap_id for data in ALL_PARTS.values()}
    checked_parts = [ap for ap in ship_ids if ap in checked]

    try:
        # Ship abilities (radar / jets): OR the bits, idempotent.
        want_flag = 0
        for ap in checked_parts:
            want_flag |= _APID_TO_EFFECT.get(ap, 0)
        if want_flag:
            addr = ps + O["mShipEffectPartFlag"]
            cur = dme.read_byte(addr)
            if (cur | want_flag) != cur:
                dme.write_byte(addr, cur | want_flag)

        # Stars per stage: number of checked parts per stage, never decreasing.
        per_stage: dict[int, int] = {}
        for ap in checked_parts:
            st = _APID_TO_STAGE.get(ap)
            if st is not None:
                per_stage[st] = per_stage.get(st, 0) + 1
        base = ps + O["mStagePartsCollected"]
        for st, count in per_stage.items():
            a = base + st  # u8 per stage
            if dme.read_byte(a) < count:
                dme.write_byte(a, count)

        # Total parts (ship upgrade, display): take the max.
        total = len(checked_parts)
        caddr = ps + O["mCurrParts"]
        cur_total = struct.unpack(">i", dme.read_bytes(caddr, 4))[0]
        if cur_total < total:
            dme.write_bytes(caddr, struct.pack(">i", total))
    except Exception:
        pass


def _detach_part_from_radar(game: Game, pellet: int) -> None:
    """Remove a part's icon from the radar (replicates RadarInfo::detachParts).

    Unlinks the mAlivePartsList node whose mPart == pellet; otherwise the radar
    keeps showing an icon for a despawned part
    (MonoObjectMgr::kill does not call Creature::kill, so no detachParts).
    """
    ptr = SYM_RADAR_INFO_PTR.get(game)
    if ptr is None:
        return
    R = RADAR_CHAIN

    def u32(addr: int) -> int:
        try:
            v = struct.unpack(">I", dme.read_bytes(addr, 4))[0]
        except Exception:
            return 0
        return v if _RAM_MIN <= v < _RAM_MAX else 0

    radar = u32(ptr)
    if not radar:
        return
    head_slot = radar + R["ALIVE_CHILD"]   # &mAlivePartsList.mChild
    node = u32(head_slot)
    prev = 0
    for _ in range(64):
        if not node:
            return
        part = u32(node + R["NODE_PART"])
        nxt = u32(node + R["NODE_NEXT"])
        if part == pellet:
            # Unlink: point the previous node (or the head slot) at the next one.
            try:
                if prev:
                    dme.write_bytes(prev + R["NODE_NEXT"], struct.pack(">I", nxt))
                else:
                    dme.write_bytes(head_slot, struct.pack(">I", nxt))
                # Detach the node and clear its mPart.
                dme.write_bytes(node + R["NODE_NEXT"], struct.pack(">I", 0))
                dme.write_bytes(node + R["NODE_PART"], struct.pack(">I", 0))
            except Exception:
                pass
            return
        prev = node
        node = nxt


def despawn_collected_part_pellets(ctx: P1Context, game: Game) -> int:
    """Despawn the Pellets of parts already checked on the server.

    Pellets are managed by pelletMgr (a MonoObjectMgr), NOT by itemMgr.
    Enumerates its active slots (mEntryStatus[i] == 0), finds ship-part pellets
    (mObjType == OBJTYPE_Pellet and known mConfig->mModelId) and removes them if
    the location is already checked:
      - mIsAlive = 0 (invisible immediately);
      - mEntryStatus[i] = -2 -> MonoObjectMgr::update calls kill() (clean removal
        by the game on the next update).
    Returns the number of parts removed.
    """
    mgr_ptr = SYM_PELLET_MGR_PTR.get(game)
    if mgr_ptr is None:
        return 0
    P = PELLET_CHAIN

    def u32(addr: int) -> int:
        try:
            v = int.from_bytes(dme.read_bytes(addr, 4), "big")
        except Exception:
            return 0
        return v if _RAM_MIN <= v < _RAM_MAX else 0

    mgr = u32(mgr_ptr)
    if not mgr:
        return 0
    obj_list = u32(mgr + P["MONO_OBJECTLIST"])
    entry_status = u32(mgr + P["MONO_ENTRYSTATUS"])
    if not obj_list or not entry_status:
        return 0
    try:
        max_elems = int.from_bytes(dme.read_bytes(mgr + P["MONO_MAXELEMENTS"], 4), "big", signed=True)
    except Exception:
        return 0
    if not (0 < max_elems <= 4096):
        return 0

    removed = 0
    for i in range(max_elems):
        try:
            status = int.from_bytes(dme.read_bytes(entry_status + i * 4, 4), "big", signed=True)
        except Exception:
            continue
        if status != 0:  # inactive slot
            continue
        creature = u32(obj_list + i * 4)
        if not creature:
            continue
        try:
            obj_type = int.from_bytes(
                dme.read_bytes(creature + ONION_CHAIN["CREATURE_OBJTYPE"], 4), "big", signed=True
            )
        except Exception:
            continue
        if obj_type != OBJTYPE_PELLET:
            continue
        config = u32(creature + P["PELLET_CONFIG"])
        if not config:
            continue
        try:
            model_id = dme.read_bytes(config + P["PELLETCONFIG_MODELID"], 4)
        except Exception:
            continue
        ap_id = _MODELID_TO_AP_ID.get(model_id)
        if ap_id is None or ap_id not in ctx.checked_locations:
            continue
        # Part already checked on the server but still present: remove it.
        try:
            # Remove the radar icon (the manager kill does not do it).
            _detach_part_from_radar(game, creature)
            dme.write_byte(creature + P["PELLET_ISALIVE"], 0)
            dme.write_bytes(entry_status + i * 4, struct.pack(">i", ENTRYSTATUS_KILL))
            removed += 1
            if ctx.debug_hint:
                logger.info(f"[DEBUG] Part pellet removed "
                            f"(slot={i}, model={model_id!r}, ap_id={ap_id})")
        except Exception:
            pass

    return removed


# Size of the object region scanned to find the fourCC of the part a creature
# holds. The UfoPartID is NOT at the same offset for every class
# (OBJTYPE_Snake: +0x31C; OBJTYPE_Teki: +0x5D0), so we scan instead of
# hardcoding an offset. Read-only (identification).
_CREATURE_SCAN_LEN = 0x600


def _held_ufo_part_ap(obj: int) -> "Optional[int]":
    """Return the ap_id of the part HELD by a creature shown on the radar, or None.

    Scans the object for the part's fourCC (e.g. b'uf06'). A creature holds only
    one part, so an ap_id is returned only if exactly ONE known part id is found
    (otherwise ambiguous -> None, to be safe).
    """
    try:
        blob = dme.read_bytes(obj, _CREATURE_SCAN_LEN)
    except Exception:
        return None
    known = _MODELID_TO_AP_ID
    found: set = set()
    for off in range(0, len(blob) - 3, 4):
        w = blob[off:off + 4]
        ap = known.get(w)
        if ap is not None:
            found.add(ap)
    return next(iter(found)) if len(found) == 1 else None


def despawn_collected_parts_on_radar(ctx: P1Context, game: Game) -> int:
    """Remove from the radar server-checked parts still shown because they are
    held INSIDE a monster/boss.

    despawn_collected_part_pellets() only handles ACTIVE pelletMgr slots
    (mEntryStatus == 0). When a part is held by a creature there is no Pellet in
    the pelletMgr at all: the radar node points to the CREATURE
    (mPart = OBJTYPE_Snake, etc.), which stores the part's UfoPartID (e.g. at
    +0x31C).

    Walks the radar list (mAlivePartsList) and distinguishes two cases:
      - node -> Pellet (free part still listed): kill it cleanly
        (mIsAlive = 0 + mEntryStatus = -2 via its slot), then unlink the node;
      - node -> Creature holding a checked part: only unlink the radar node (the
        icon disappears). The creature is NOT touched: if killed later it drops an
        already-collected pellet that the regular loop will remove.
    Returns the number of icons removed.
    """
    ptr = SYM_RADAR_INFO_PTR.get(game)
    if ptr is None:
        return 0
    R = RADAR_CHAIN
    P = PELLET_CHAIN

    def u32(addr: int) -> int:
        try:
            v = int.from_bytes(dme.read_bytes(addr, 4), "big")
        except Exception:
            return 0
        return v if _RAM_MIN <= v < _RAM_MAX else 0

    radar = u32(ptr)
    if not radar:
        return 0

    known_models = _MODELID_TO_AP_ID

    # 1) Read-only walk of the radar list (not modified here).
    pellets_to_kill: list[int] = []   # free pellets: kill + detach
    creatures_to_detach: list[int] = []  # creatures holding a part: detach only
    node = u32(radar + R["ALIVE_CHILD"])
    for _ in range(128):  # loop guard
        if not node:
            break
        obj = u32(node + R["NODE_PART"])
        nxt = u32(node + R["NODE_NEXT"])
        if obj:
            try:
                obj_type = int.from_bytes(
                    dme.read_bytes(obj + ONION_CHAIN["CREATURE_OBJTYPE"], 4),
                    "big", signed=True,
                )
            except Exception:
                obj_type = -1

            if obj_type == OBJTYPE_PELLET:
                config = u32(obj + P["PELLET_CONFIG"])
                model_id = None
                if config:
                    try:
                        model_id = dme.read_bytes(config + P["PELLETCONFIG_MODELID"], 4)
                    except Exception:
                        model_id = None
                ap_id = known_models.get(model_id) if model_id else None
                if ap_id is not None and ap_id in ctx.checked_locations and obj not in pellets_to_kill:
                    pellets_to_kill.append(obj)
            else:
                # A creature shown on the parts radar holds a part. Its UfoPartID
                # (fourCC) sits at a class-dependent offset, so scan the object.
                ap_id = _held_ufo_part_ap(obj)
                if ap_id is not None and ap_id in ctx.checked_locations and obj not in creatures_to_detach:
                    creatures_to_detach.append(obj)
        node = nxt

    if not pellets_to_kill and not creatures_to_detach:
        return 0

    # 2) For free pellets: locate each target in the pelletMgr (by pointer) to
    #    kill it cleanly via its slot, like the regular loop.
    slot_of: dict[int, int] = {}
    entry_status = 0
    if pellets_to_kill:
        mgr_ptr = SYM_PELLET_MGR_PTR.get(game)
        if mgr_ptr is not None:
            mgr = u32(mgr_ptr)
            if mgr:
                obj_list = u32(mgr + P["MONO_OBJECTLIST"])
                entry_status = u32(mgr + P["MONO_ENTRYSTATUS"])
                try:
                    max_elems = int.from_bytes(
                        dme.read_bytes(mgr + P["MONO_MAXELEMENTS"], 4), "big", signed=True
                    )
                except Exception:
                    max_elems = 0
                if obj_list and entry_status and 0 < max_elems <= 4096:
                    targets = set(pellets_to_kill)
                    for i in range(max_elems):
                        c = u32(obj_list + i * 4)
                        if c in targets:
                            slot_of[c] = i

    removed = 0

    # 3a) Free pellets: radar icon + pellet kill.
    for pellet in pellets_to_kill:
        try:
            _detach_part_from_radar(game, pellet)
            dme.write_byte(pellet + P["PELLET_ISALIVE"], 0)
            idx = slot_of.get(pellet)
            if idx is not None and entry_status:
                dme.write_bytes(entry_status + idx * 4, struct.pack(">i", ENTRYSTATUS_KILL))
            removed += 1
            if ctx.debug_hint:
                logger.info(f"[DEBUG] Part (free pellet) removed from radar "
                            f"pellet=0x{pellet:08X}, slot={idx}")
        except Exception:
            pass

    # 3b) Parts held by a creature: only unlink the radar node.
    for creature in creatures_to_detach:
        try:
            _detach_part_from_radar(game, creature)
            removed += 1
            if ctx.debug_hint:
                logger.info(f"[DEBUG] Part icon removed from radar (held inside "
                            f"an enemy) creature=0x{creature:08X}")
        except Exception:
            pass

    return removed


def _fix_zombie_olimar(game: Game) -> None:
    """Re-trigger a lost death: Olimar has <= 1 HP, orimaDead is 0 and he is in a normal state."""
    if read_orima_dead(game):
        return
    navi = _resolve_olimar(game)
    if navi is None:
        return
    try:
        hp = struct.unpack(">f", dme.read_bytes(navi + NAVI_CHAIN["CREATURE_HEALTH"], 4))[0]
    except Exception:
        return
    if hp <= 1.0:
        kill_olimar(game)  # does nothing unless Olimar is in NaviWalkState


def _free_play_elapsed(ctx, game: Game, attr: str) -> bool:
    """Return True after CONE_START_DELAY seconds of free play (no cutscene, no menu).

    `attr`: ctx attribute storing the start of the free-play period (reset to
    None whenever a cutscene or menu interrupts the game)."""
    if is_movie_playing(game) or is_overlay_active(game):
        setattr(ctx, attr, None)
        return False
    now = time.monotonic()
    since = getattr(ctx, attr, None)
    if since is None:
        setattr(ctx, attr, now)
        return False
    return now - since >= CONE_START_DELAY


async def detect_olimar_death(ctx: "P1Context", game: Game) -> None:
    """DeathLink classic/both: send on the rising edge of orimaDead.

    Once a monster kills Olimar the game pauses and chains into the death /
    end-of-day sequence (mIsPauseAllowed = FALSE), so the in-game handlers stop
    running. This detection therefore runs every tick while in a level, whether
    or not the day is active. Read-only (plus network send).
    """
    if ctx.death_link_mode not in (1, 3):
        return
    is_dead = read_orima_dead(game)
    if is_dead and not ctx._orima_was_dead:
        if ctx._suppress_orima_send:
            # Death caused by a received DeathLink (or by the pikmin threshold in
            # both mode, or by the client): consume it without re-sending.
            ctx._suppress_orima_send = False
        elif not ctx._deathlink_locked_this_day:
            await ctx.send_death(olimar_death_message(ctx, game))
            ctx._deathlink_locked_this_day = True
    ctx._orima_was_dead = is_dead


async def handle_death_link(ctx: P1Context, game: Game) -> None:
    """DeathLink: detection (send) and application (receive).

    Modes (ctx.death_link_mode):
      0 off, 1 classic, 2 pikmin, 3 both.
    Send:
      - classic / both: rising edge of orimaDead (Olimar just died).
      - pikmin  / both: every X Pikmin deaths in the day (deadPikis, already
        reset each day).
      - both: additionally, when the Pikmin threshold is reached, Olimar is
        also killed locally.
    Receive:
      - a received DeathLink (ctx.pending_kill) kills Olimar on the next in-game tick.
    """
    # --- Self-kill (both mode): consequence of our own send, not subject to the
    # lock. Retried if Olimar could not be resolved when the send happened.
    if ctx._pending_self_kill:
        if kill_olimar(game):
            ctx._pending_self_kill = False
            ctx._suppress_orima_send = True

    # Safety net for a "zombie Olimar" (0 HP but not dead: the game cancelled the
    # started death). Re-trigger it as soon as he is controllable again.
    _fix_zombie_olimar(game)

    # --- Receive: kill Olimar ---
    # Same delay as cones / traps: nothing during a cutscene or a menu, then
    # CONE_START_DELAY seconds of free play.
    if ctx.pending_kill and not ctx._deathlink_locked_this_day \
            and not _free_play_elapsed(ctx, game, "_dl_free_since"):
        pass
    elif ctx.pending_kill:
        if ctx._deathlink_locked_this_day:
            # A DeathLink event already happened today: ignore received deaths
            # until the start-of-day reset.
            ctx.pending_kill = False
        elif kill_olimar(game):
            ctx.pending_kill = False
            # The upcoming death comes from a received DeathLink: do not send it
            # back through the classic detection.
            ctx._suppress_orima_send = True
            ctx._deathlink_locked_this_day = True
            _lang = getattr(ctx, "detected_language", "en")
            logger.info(f"[Pikmin] {DEATHLINK_RECEIVED_MSG.get(_lang, DEATHLINK_RECEIVED_MSG['en'])}")
        # otherwise: Olimar not resolvable yet, retry on the next tick.

    if ctx.death_link_mode == 0:
        return

    # Safety lock: no send/receive until the day has been reset (rising edge of
    # "in a level", see dolphin_loop). Detection state keeps being tracked so no
    # deferred send fires once the lock is released.
    if ctx._deathlink_locked_this_day:
        ctx._orima_was_dead = read_orima_dead(game)
        dt = read_dead_pikis_total(game)
        if dt is not None:
            ctx._dead_pikis_last = dt
        return

    send_on_olimar = ctx.death_link_mode in (1, 3)   # classic, both
    send_on_pikmin = ctx.death_link_mode in (2, 3)   # pikmin, both
    pikmin_kills_olimar = ctx.death_link_mode == 3    # both

    # --- Send on Olimar's death: see detect_olimar_death(), which is called even
    # outside interactive gameplay because the death immediately stops the game. ---
    if send_on_olimar and ctx._deathlink_locked_this_day:
        return

    # --- Send on Pikmin deaths (every X, per day) ---
    if send_on_pikmin:
        dead_total = read_dead_pikis_total(game)
        if dead_total is None:
            return
        # deadPikis is per day, but at the very start of the day it may still be
        # residual (not yet reset). On the first read (last is None), take the
        # current value as an already-counted reference; otherwise a residual
        # count would be taken for new deaths and send a DeathLink at day start.
        # A later decrease means the game reset it, so counting restarts.
        if ctx._dead_pikis_last is None:
            ctx._dead_pikis_last = dead_total
            ctx._dead_pikis_sent = dead_total // ctx.pikmin_death_amount
        elif dead_total < ctx._dead_pikis_last:
            ctx._dead_pikis_sent = 0
            ctx._dead_pikis_last = dead_total
        else:
            ctx._dead_pikis_last = dead_total
        should_have_sent = dead_total // ctx.pikmin_death_amount
        if ctx._dead_pikis_sent < should_have_sent:
            ctx._dead_pikis_sent += 1
            await ctx.send_death(death_message(ctx, "grief"))
            ctx._deathlink_locked_this_day = True
            # Both mode: reaching the threshold also kills Olimar locally. This is
            # a consequence of OUR send (not a receive), so we kill even though the
            # lock was just set. No echo: _suppress_orima_send.
            if pikmin_kills_olimar:
                if kill_olimar(game):
                    ctx._suppress_orima_send = True
                else:
                    ctx._pending_self_kill = True  # Olimar not resolvable, retry


async def handle_pikmin_bond(ctx: P1Context, game: Game) -> None:
    """Olimar/Pikmin bond: each dead Pikmin removes HP from Olimar.

    Source: GameStat::deadPikis (sum of the 3 colors, reset each day). As with
    the "pikmin" DeathLink, the first read of the day is the reference (it may
    be residual); a decrease means the game reset it -> new reference.

    At 0 HP (the game's death threshold: <= 1.0), kill_olimar() is used to
    trigger the REAL death sequence (writing mHealth alone is not enough).
    Classic DeathLink detection then sends a DeathLink if enabled.
    Only runs during interactive gameplay (in_level_handlers).
    """
    if not ctx.pikmin_bond:
        return
    # Pending bond death: Olimar was not controllable (thrown, crushed,
    # whistling...) so kill_olimar() refused. Retry every tick.
    if ctx._bond_kill_pending:
        if read_orima_dead(game):
            ctx._bond_kill_pending = False
        elif kill_olimar(game):
            ctx._bond_kill_pending = False
            ctx._client_kill_reason = "Pikmin Bond"
            await report_client_kill(ctx)
    dead_total = read_dead_pikis_total(game)
    if dead_total is None:
        return
    last = ctx._bond_dead_last
    ctx._bond_dead_last = dead_total
    if last is None or dead_total <= last:
        return  # reference / reset / nothing new
    if read_orima_dead(game):
        return  # already down: nothing to remove

    navi = _resolve_olimar(game)
    if navi is None:
        # Olimar not resolvable: keep the old reference so these deaths are
        # applied on the next tick.
        ctx._bond_dead_last = last
        return
    deaths = dead_total - last
    loss = ctx.pikmin_bond_damage * deaths
    addr = navi + NAVI_CHAIN["CREATURE_HEALTH"]
    try:
        h = struct.unpack(">f", dme.read_bytes(addr, 4))[0]
    except Exception:
        ctx._bond_dead_last = last
        return
    new = h - loss
    if ctx.debug_trap:
        logger.info(f"[DEBUG BOND] {deaths} Pikmin death(s): HP {h:.1f} -> {max(new, 0.0):.1f}")
    if new <= 1.0:
        # Olimar dies through the bond: real in-game death sequence. If Olimar is
        # not controllable right now, the death stays pending.
        if kill_olimar(game):
            ctx._client_kill_reason = "Pikmin Bond"
            await report_client_kill(ctx)
        else:
            ctx._bond_kill_pending = True
    else:
        try:
            dme.write_bytes(addr, struct.pack(">f", new))
        except Exception as e:
            logger.debug(f"Error writing bond damage: {e}")


OLIMAR_MAX_HEALTH = 100.0


async def handle_olimar_bond(ctx: P1Context, game: Game) -> None:
    """Olimar Bond: each newly born Pikmin heals Olimar (olimar_bond_heal % of
    his max health, capped at 100).

    Source: GameStat::bornPikis ("sprouts today"), which counts seeds coming out
    of the onions AND received Pikmin bonuses (during the day, or at the start
    of the next day if they arrive on the map). As with the Olimar/Pikmin bond:
    first read of the day = reference, a decrease = reset by the game.
    """
    slot_data = getattr(ctx, "slot_data", None) or {}
    if not slot_data.get("olimar_bond", 0):
        return
    base = SYM_BORN_PIKIS.get(game)
    if base is None:
        return
    try:
        born = sum(struct.unpack(">iii", dme.read_bytes(base, 12)))
    except Exception:
        return
    last = ctx._olimar_bond_last
    ctx._olimar_bond_last = born
    if last is None or born <= last:
        return
    if read_orima_dead(game):
        return
    navi = _resolve_olimar(game)
    if navi is None:
        ctx._olimar_bond_last = last  # retry on the next tick
        return
    heal = OLIMAR_MAX_HEALTH * float(slot_data.get("olimar_bond_heal", 1)) / 100.0 * (born - last)
    addr = navi + NAVI_CHAIN["CREATURE_HEALTH"]
    try:
        h = struct.unpack(">f", dme.read_bytes(addr, 4))[0]
        if h <= 1.0:
            return  # already down: no resurrection
        new = min(OLIMAR_MAX_HEALTH, h + heal)
        if new > h:
            dme.write_bytes(addr, struct.pack(">f", new))
            if ctx.debug_trap:
                logger.info(f"[DEBUG BOND] {born - last} Pikmin born: HP {h:.1f} -> {new:.1f}")
    except Exception as e:
        logger.debug(f"olimar bond: {e}")


# Trap item id -> internal kind, built once.
_TRAP_ID_TO_KIND = {TRAP_ITEMS[name]: TRAP_KINDS[name] for name in TRAP_ITEMS}
_TRAP_KIND_TO_NAME = {TRAP_KINDS[name]: name for name in TRAP_ITEMS}


async def handle_traps(ctx: P1Context, game: Game) -> None:
    """Apply received traps (AP items) and those received via TrapLink.

    One trap per tick. Item traps are persisted (traps_applied) so they are not
    replayed on restart; TrapLink traps are transient (pending_trap_links queue).
    """
    # Apply NO trap until the day has really started: during level select,
    # loading and the intro cutscene the player does not control Olimar
    # (mIsPauseAllowed FALSE). Olimar must also be resolvable. Traps received in
    # the meantime stay pending (items_received / pending_trap_links) and are
    # applied once the day is really running.
    if not is_day_active(game) or _resolve_olimar(game) is None:
        return

    # Post End-Day-Trap lock: no trap until the next day has started (released on
    # the rising edge of "in a level", see dolphin_loop).
    if ctx._traps_suspended_until_next_day:
        return

    # Pause menu / map / text window / onion menu open: suspend everything (AP
    # and TrapLink traps stay queued). On close, re-arm a grace delay (~3 s)
    # before applying the pending trap.
    if is_overlay_active(game):
        ctx._trap_overlay_was_active = True
        ctx._trap_free_since = None
        return
    # Like cones: no trap during a cutscene, then CONE_START_DELAY seconds of free
    # play (including after the start-of-day cutscene) before the first trap.
    if is_movie_playing(game):
        ctx._trap_free_since = None
        return
    _now = time.monotonic()
    if ctx._trap_free_since is None:
        ctx._trap_free_since = _now
    if _now - ctx._trap_free_since < CONE_START_DELAY:
        return
    if ctx._trap_overlay_was_active:
        ctx._trap_overlay_was_active = False
        ctx._trap_grace_ticks = max(ctx._trap_grace_ticks, 3)
        if ctx.debug_trap:
            logger.info("[DEBUG TRAP] Menu closed: traps resume after the grace delay.")

    # Grace delay at the very start of the day (active gameplay): avoids wasting
    # a trap right after landing.
    if ctx._trap_grace_ticks > 0:
        ctx._trap_grace_ticks -= 1
        return

    # 1) Traps received as AP items.
    for item in ctx.items_received:
        item_id = item.item
        kind = _TRAP_ID_TO_KIND.get(item_id)
        if kind is None:
            continue
        total = sum(1 for i in ctx.items_received if i.item == item_id)
        already = ctx.traps_applied.get(item_id, 0)
        if total <= already:
            continue
        # Player who sent THIS trap (the (already+1)-th occurrence).
        occ = [i for i in ctx.items_received if i.item == item_id][already]
        ctx._trap_source = (ctx.player_names.get(occ.player)
                            if getattr(occ, "player", ctx.slot) != ctx.slot else None)
        if await apply_trap(game, kind, ctx):
            ctx.traps_applied[item_id] = already + 1  # one at a time
            ctx.save_applied()
            name = _TRAP_KIND_TO_NAME.get(kind, kind)
            if ctx.debug_trap:
                logger.info(f"[DEBUG TRAP] Trap applied: {name}")
            # TrapLink: broadcast the trap we just suffered to the others.
            if ctx.trap_link_enabled:
                await ctx.send_trap_link(name)
            # End Day Trap: the day is about to end; freeze traps until the next
            # one so a second trap is not applied during the end-of-day window
            # (which would send the player back to the menu without saving).
            if kind == "end_day":
                ctx._traps_suspended_until_next_day = True
            return  # only one trap per tick

    # 2) Traps received via TrapLink (transient).
    if ctx.pending_trap_links:
        name = ctx.pending_trap_links[0]
        kind = TRAP_KINDS.get(name)
        if kind is None:
            ctx.pending_trap_links.pop(0)
            if ctx.pending_trap_link_sources:
                ctx.pending_trap_link_sources.pop(0)
            return
        ctx._trap_source = ctx.pending_trap_link_sources[0] if ctx.pending_trap_link_sources else None
        if await apply_trap(game, kind, ctx):
            ctx.pending_trap_links.pop(0)
            if ctx.pending_trap_link_sources:
                ctx.pending_trap_link_sources.pop(0)
            if ctx.debug_trap:
                logger.info(f"[DEBUG TRAP] TrapLink trap applied: {name}")
            if kind == "end_day":
                ctx._traps_suspended_until_next_day = True
        # otherwise: not applicable now, retry on the next tick.


# --- Custom Save --------------------------------------------------------------
#
# The "Pikmin bonuses already applied" state is stored client-side only
# (_persistent_storage.yaml, per AP slot). On a new game, another game save slot
# (A/B/C) or after reloading an older save, bonuses would not be re-applied (or
# the state would no longer match the game).
#
# The game save has no usable free space (only PlayerState::_186 is saved
# without being used, and it is normalized to 0/1 on load). So each save is
# identified by its checksum (gameflow.mSaveGameCrc): read from the card when a
# file is chosen and recomputed on every save. For each checksum the client
# remembers the bonuses applied AT THE TIME of that save:
#   - loading a file (CardSelect -> game):
#       * new game (mSavedDay == 1)  -> nothing applied: everything is re-applied;
#       * known checksum             -> state of that save (bonuses applied but
#                                       not saved will be re-applied);
#       * unknown checksum (save older than this feature) -> current state kept.
#   - saving (checksum changes in game) -> the current state is recorded.
# Copying a file to another slot gives the same checksum: the state follows.

_ONEPLAYER_CARD_SELECT = 1
_ONEPLAYER_INTRO_GAME = 5
_SAVE_TRACK_SUBSECTIONS = (_ONEPLAYER_INTRO_GAME, ONEPLAYER_MAP_SELECT, ONEPLAYER_NEW_PIKI_GAME)
# Sub-sections where the "always" handlers may write to RAM.
_STORY_SUBSECTIONS = (_ONEPLAYER_CARD_SELECT, _ONEPLAYER_INTRO_GAME, ONEPLAYER_MAP_SELECT, ONEPLAYER_NEW_PIKI_GAME)
MAX_TRACKED_SAVES = 60

# Messages per detected game language (like SYNC_ACTIVE_MSG).
SAVE_LOADED_MSG = {
    "new": {
        "en": "New game (file {slot}): every Pikmin bonus received will be applied.",
        "fr": "Nouvelle partie (fichier {slot}) : tous les bonus Pikmin reçus seront appliqués.",
        "de": "Neues Spiel (Datei {slot}): alle erhaltenen Pikmin-Boni werden angewendet.",
        "it": "Nuova partita (file {slot}): tutti i bonus Pikmin ricevuti verranno applicati.",
        "es": "Nueva partida (archivo {slot}): se aplicarán todos los bonus de Pikmin recibidos.",
    },
    "known": {
        "en": "Save recognized (file {slot}): Pikmin bonuses not yet saved will be re-applied.",
        "fr": "Sauvegarde reconnue (fichier {slot}) : les bonus Pikmin non sauvegardés seront réappliqués.",
        "de": "Spielstand erkannt (Datei {slot}): noch nicht gespeicherte Pikmin-Boni werden erneut angewendet.",
        "it": "Salvataggio riconosciuto (file {slot}): i bonus Pikmin non ancora salvati verranno riapplicati.",
        "es": "Partida reconocida (archivo {slot}): se volverán a aplicar los bonus de Pikmin no guardados.",
    },
    "unknown": {
        "en": "Untracked save (file {slot}, created before this version): current state kept.",
        "fr": "Sauvegarde non suivie (fichier {slot}, créée avant cette version) : état actuel conservé.",
        "de": "Nicht verfolgter Spielstand (Datei {slot}, vor dieser Version erstellt): aktueller Stand bleibt erhalten.",
        "it": "Salvataggio non tracciato (file {slot}, creato prima di questa versione): stato attuale mantenuto.",
        "es": "Partida no registrada (archivo {slot}, creada antes de esta versión): se mantiene el estado actual.",
    },
}


def _read_u32_opt(addr: int) -> Optional[int]:
    try:
        return struct.unpack(">I", dme.read_bytes(addr, 4))[0]
    except Exception:
        return None


def track_game_save(ctx: P1Context, game: Game) -> None:
    """Track game loads and saves (see block above)."""
    gf = SYM_GAMEFLOW.get(game)
    if not gf:
        return
    sub = _oneplayer_subsection(game)
    prev = ctx._save_prev_sub
    ctx._save_prev_sub = sub
    connected = bool(ctx.auth) and bool(getattr(ctx, "slot_data", None))

    if sub in _SAVE_TRACK_SUBSECTIONS:
        crc = _read_u32_opt(gf["SAVE_GAME_CRC"])
        if crc is not None:
            if prev == _ONEPLAYER_CARD_SELECT:
                # A file was just chosen (new game or load).
                # New game = PlayState.mSavedDay == 1: a blank file keeps day 1
                # from PlayState::Initialise, while any save happens after moving
                # to the next day (>= 2).
                # (mSaveStatus is NOT reliable: CardSelect sets it to ReadyToSave
                # as soon as a blank file is chosen.)
                try:
                    saved_day = dme.read_byte(gf["PLAYSTATE_SAVED_DAY"])
                except Exception:
                    saved_day = None
                slot = _read_u32_opt(gf["FILE_SLOT"])
                if ctx.debug_pbonus:
                    logger.info(f"[DEBUG] File chosen: crc={crc:08X} savedDay={saved_day} slot={slot}")
                ctx._pending_save_load = (crc, saved_day == 1,
                                          (slot + 1) if slot is not None and slot < 3 else "?")
                ctx._save_crc = crc
            elif ctx._save_crc is None:
                # Client started (or reconnected) mid-game: continuation.
                ctx._save_crc = crc
            elif crc != ctx._save_crc:
                # The game just saved: freeze the state for this checksum.
                ctx._save_crc = crc
                if connected and ctx._pending_save_load is None:
                    key = f"{crc:08X}"
                    ctx.game_saves.pop(key, None)  # re-insert at the end (most recent)
                    ctx.game_saves[key] = {str(k): v for k, v in ctx.pikmin_items_applied.items()}
                    ctx.store_game_saves()
                    if ctx.debug_pbonus:
                        logger.info(f"[DEBUG] Game save {key}: bonus state recorded.")

    # Resolve the load (waits for the server connection if needed).
    if ctx._pending_save_load is not None and connected:
        crc, fresh, slot = ctx._pending_save_load
        ctx._pending_save_load = None
        key = f"{crc:08X}"
        if fresh:
            ctx.pikmin_items_applied = {}
            kind = "new"
        elif key in ctx.game_saves:
            ctx.pikmin_items_applied = {int(k): v for k, v in ctx.game_saves[key].items()}
            kind = "known"
        else:
            kind = "unknown"
        _lang = getattr(ctx, "detected_language", "en")
        _msgs = SAVE_LOADED_MSG[kind]
        logger.info("[Pikmin] " + _msgs.get(_lang, _msgs["en"]).format(slot=slot))
        ctx.save_applied()


# --- Pikmin bonus items counted as "sprouts" -----------------------------------
_BORN_COLOR_INDEX = {"blue": 0, "red": 1, "yellow": 2}  # ColCounter / PikiNum


def _add_born_pikis(game: Game, color: str, amount: int) -> bool:
    """GameStat::bornPikis[color] += amount ("sprouts today").

    At the end of the day the game adds bornPikis to PlayerState::mSproutedNum
    (total sprouts) and to the global record (updateFinalResult) by itself, so
    those totals do not need to be written here.
    """
    base = SYM_BORN_PIKIS.get(game)
    if base is None:
        return False
    addr = base + _BORN_COLOR_INDEX[color] * 4
    try:
        old = struct.unpack(">i", dme.read_bytes(addr, 4))[0]
        dme.write_bytes(addr, struct.pack(">i", max(0, old + amount)))
        return True
    except Exception:
        return False


def _update_population_graph(game: Game) -> None:
    """Update the current hour's point of the population graph
    (PlayerState::mPerHourGraph) with GameStat::allPikis, as
    PlayerState::update() does on each hour change."""
    ps_ptr = SYM_PLAYER_STATE_PTR.get(game)
    gf = SYM_GAMEFLOW.get(game)
    allp = GAMESTAT_ALLPIKIS_ADDRS.get(game, {})
    if ps_ptr is None or not gf or not allp:
        return
    try:
        ps = struct.unpack(">I", dme.read_bytes(ps_ptr, 4))[0]
        if not (_RAM_MIN <= ps < _RAM_MAX):
            return
        g = ps + PLAYERSTATE_OFFSETS["mPerHourGraph"]
        start, end = struct.unpack(">HH", dme.read_bytes(g, 4))
        entries = struct.unpack(">I", dme.read_bytes(g + 4, 4))[0]
        if not (_RAM_MIN <= entries < _RAM_MAX) or end < start or end - start > 24:
            return
        hour = struct.unpack(">i", dme.read_bytes(gf["TIME_HOURS"], 4))[0]
        if not (start <= hour <= end):
            return
        entry = entries + (hour - start) * 12
        for color, idx in _BORN_COLOR_INDEX.items():
            a = allp.get(color)
            if a is None:
                continue
            val = struct.unpack(">i", dme.read_bytes(a, 4))[0]
            dme.write_bytes(entry + idx * 4, struct.pack(">i", val))
    except Exception as e:
        logger.debug(f"population graph update: {e}")


def flush_pending_born(ctx: P1Context, game: Game) -> None:
    """Count bonuses received outside a day (world map, between days) as the
    day's sprouts once the new day has actually started (GameStat is reset
    when the level loads)."""
    if not any(ctx._pending_born.values()):
        return
    if not (is_in_level(game) and is_day_active(game)):
        return
    for color, n in ctx._pending_born.items():
        if n and _add_born_pikis(game, color, n):
            ctx._pending_born[color] = 0
            if ctx.debug_pbonus:
                logger.info(f"[DEBUG] bornPikis {color} +{n} (bonus received outside a day)")


async def handle_pikmin_items(ctx: P1Context, game: Game) -> None:
    """Apply received Pikmin bonus items.

    Two writes per item:
    1. Stage persistent (0x803D6C7x) — survives day transitions, read by game at day start.
    2. Dynamic onion RAM (base_red + 0x10/14/18) — visible immediately in-game.
       base_red is found by scanning RAM at day-start (sentinel 0->nonzero) and matching
       the known persistent Leaf/Bud/Flower values at offsets +0x10/+0x14/+0x18.
       Yellow/Blue dynamic TBD — only Red enabled for now.
    """
    if game not in ONION_STAGE_ADDRS_CLIENT:
        return
    # Save just loaded, state not resolved yet: wait.
    if ctx._pending_save_load is not None:
        return
    # Bonuses received outside a day become sprouts of the current day.
    flush_pending_born(ctx, game)

    stage_addrs   = ONION_STAGE_ADDRS_CLIENT[game]
    sentinel_addr = ONION_DYN_SENTINEL.get(game)

    id_to_pikmin: dict[int, tuple[str, str, int]] = {
        FILLER_ITEMS[name]: PIKMIN_BONUS_ITEMS[name]
        for name in PIKMIN_BONUS_ITEMS
        if name in FILLER_ITEMS
    }

    def read_u32(addr: int) -> int:
        try:
            return int.from_bytes(dme.read_bytes(addr, 4), "big")
        except Exception:
            return 0

    def write_u32(addr: int, value: int) -> None:
        try:
            dme.write_bytes(addr, max(0, value).to_bytes(4, "big"))
        except Exception as e:
            logger.debug(f"Error writing u32 to 0x{addr:08x}: {e}")

    # Detect day-start: sentinel 0 -> nonzero.
    # 0x803D6D20 stays zero until the first day is loaded (even on title screen).
    day_start_detected = False
    if sentinel_addr is not None:
        sentinel_val = read_u32(sentinel_addr)
        sentinel_zero = (sentinel_val == 0)
        if ctx._onion_dyn_was_zero and not sentinel_zero:
            day_start_detected = True
            if ctx.debug_pbonus:
                logger.info(
                    f"[DEBUG] Day start detected (sentinel 0->0x{sentinel_val:08X})"
                )
        ctx._onion_dyn_was_zero = sentinel_zero

    # GoalItem::mHeldPikis[Leaf/Bud/Flower] at _0x42C.
    _HELD = ONION_CHAIN["GOAL_HELDPIKIS"]
    DYN_OFFSETS = {"leaf": _HELD + 0x0, "bud": _HELD + 0x4, "flower": _HELD + 0x8}
    DYN_BASE_CACHE = {"red": "_dyn_base_red", "yellow": "_dyn_base_yellow", "blue": "_dyn_base_blue"}

    # Resolve onions through a pointer chain. Cheap enough to redo at every day
    # start; objects are reallocated on each load, so never keep a cache
    # across days.
    if day_start_detected:
        containers = find_onion_containers(game)
        for color in ("red", "yellow", "blue"):
            addr = containers.get(color)
            setattr(ctx, DYN_BASE_CACHE[color], addr)
            if ctx.debug_pbonus:
                if addr:
                    logger.info(f"[DEBUG] onion {color} @ 0x{addr:08X}")
                else:
                    logger.info(f"[DEBUG] onion {color} not found")

    # In-game = sentinel nonzero AND DAY_NUMBER != 0
    try:
        current_day = dme.read_byte(DAY_NUMBER[game])
    except Exception:
        current_day = 0
    # Only write into the LIVE onion (heap object, DYN) during interactive
    # gameplay. During in-level cutscenes (day intro, goal ending sequence) the
    # object is torn down / reused by rendering, and writing to it corrupts the
    # GPU stream. Persistence goes through STAGE (source of truth) anyway.
    # The "sentinel" (gameflow+0x2EC) is WorldClock.mRealSecsIntoHour: it drops
    # to 0 on every hour change and stays 0 while the clock is frozen (start of
    # day 1), so it is not usable as a gate. Use the real game state instead
    # (level loaded + day active).
    in_game = (current_day != 0) and is_in_level(game) and is_day_active(game)

    def add_pikmin(color: str, stage: str, amount: int) -> bool:
        """Apply a bonus. Always returns True.

        The persistent counter (STAGE) is the source of truth and is always
        incremented immediately, whether or not this color's onion is loaded
        in memory (it only is when the player is in the area containing it,
        never on the world map for example).

        The live sync into the onion (DYN, mHeldPikis) is best-effort when in
        game and the onion is resolved; its failure never blocks the STAGE write.
        """
        s_addr = stage_addrs[color][stage]
        old_s = read_u32(s_addr)
        write_u32(s_addr, old_s + amount)
        if ctx.debug_pbonus:
            logger.info(
                f"[DEBUG] STAGE 0x{s_addr:08X} {color}/{stage} : {old_s} -> {old_s + amount} (+{amount})"
            )

        # GameStat::containerPikis and GameStat::allPikis (per color, all
        # stages) feed the real-time HUD total (mTotalPikiNum) and the results
        # screen.
        container_addr = ONION_DYN_ADDRS.get(game, {}).get(color)
        if container_addr is not None:
            old_c = read_u32(container_addr)
            write_u32(container_addr, old_c + amount)
        allpikis_addr = GAMESTAT_ALLPIKIS_ADDRS.get(game, {}).get(color)
        if allpikis_addr is not None:
            old_a = read_u32(allpikis_addr)
            write_u32(allpikis_addr, old_a + amount)
        if ctx.debug_pbonus:
            logger.info(
                f"[DEBUG] LIVE TOTAL {color} : containerPikis +{amount}, allPikis +{amount}"
            )

        # The bonus counts as sprouted Pikmin (end-of-day screen) and shows up
        # in the population graph immediately. Outside a day (world map...)
        # GameStat is reset on the next load, so queue it and let
        # flush_pending_born() add it at the start of the next day.
        if in_game and is_in_level(game):
            if not _add_born_pikis(game, color, amount):
                ctx._pending_born[color] += amount
            _update_population_graph(game)
        else:
            ctx._pending_born[color] += amount

        if in_game and stage in DYN_OFFSETS:
            # Do not trust the address cached at day start (the sentinel may
            # not go through 0 on day 1 or some reloads, leaving a stale freed
            # onion). Resolve the LIVE onion on every application (rare event,
            # cheap lookup).
            base = find_onion_containers(game).get(color)
            setattr(ctx, DYN_BASE_CACHE[color], base)
            if base:
                d_addr = base + DYN_OFFSETS[stage]
                old_d = read_u32(d_addr)
                write_u32(d_addr, old_d + amount)
                if ctx.debug_pbonus:
                    logger.info(
                        f"[DEBUG] DYN   0x{d_addr:08X} {color}/{stage} : {old_d} -> {old_d + amount} (+{amount})"
                    )
            elif ctx.debug_pbonus:
                logger.info(
                    f"[DEBUG] {color}/{stage} +{amount} : onion not resolved, "
                    f"STAGE updated instantly, live DYN sync skipped this tick"
                )

        if not in_game and ctx.debug_pbonus:
            # Explain why the live onion write is skipped.
            logger.info(
                f"[DEBUG] {color}/{stage} +{amount} : live onion sync skipped "
                f"(day={current_day} in_level={is_in_level(game)} "
                f"day_active={is_day_active(game)} sub={_oneplayer_subsection(game)})"
            )
        return True

    for item in ctx.items_received:
        item_id = item.item
        if item_id not in id_to_pikmin:
            continue

        color, stage, count = id_to_pikmin[item_id]
        total_received = sum(1 for i in ctx.items_received if i.item == item_id)
        already_applied = ctx.pikmin_items_applied.get(item_id, 0)
        to_apply = total_received - already_applied
        if to_apply <= 0:
            continue

        bonus = count * to_apply
        if ctx.debug_pbonus:
            logger.info(f"[DEBUG] Item  {color}/{stage} +{bonus} (item_id={item_id})")
        # Only mark the item as applied if the write durably succeeded;
        # otherwise retry on the next tick so received Pikmin are not lost.
        if add_pikmin(color, stage, bonus):
            ctx.pikmin_items_applied[item_id] = total_received

    ctx.save_applied()


async def _create_super_radar_hint(ctx: P1Context, part_name: str) -> None:
    """Create the Super Radar hint (location of the player's part) for part_name.

    Reuses the slot_data hints (like handle_ship_part_hints). No-op if no hint
    is available or it was already created.
    """
    slot_hints: dict = (ctx.slot_data or {}).get("hints", {})
    hint_data = slot_hints.get(f"{part_name}_radar") or slot_hints.get(part_name)
    if not hint_data:
        return
    key = f"{part_name}_radar"
    if key in ctx.created_hints:
        return
    try:
        target_loc_id = int(hint_data.get("Location ID", 0))
        target_player = int(hint_data.get("Send Player ID", ctx.slot))
    except (ValueError, TypeError):
        return
    if not target_loc_id:
        return
    ctx.created_hints.add(key)
    await ctx.send_msgs([{
        "cmd": "CreateHints",
        "locations": [target_loc_id],
        "player": target_player,
    }])
    if ctx.debug_hint:
        logger.info(f"[DEBUG] Super Radar hint created for {part_name} "
                    f"(part collected server-side)")


async def handle_parts(ctx: P1Context, game: Game):
    slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
    hint_mode = slot_data.get("ship_part_hint_mode", 0)

    # Physically despawn parts checked server-side (e.g. another game finished)
    # but not picked up in-game. One pass per tick.
    despawn_collected_part_pellets(ctx, game)
    # Same for parts held INSIDE a monster/boss, which the loop above skips
    # (pelletMgr slot not active): use the radar list to remove their icon and
    # kill them.
    despawn_collected_parts_on_radar(ctx, game)
    # Update ship capabilities (radar/jets) and per-level stars for parts
    # checked server-side (which the game did not register).
    sync_playerstate_parts(ctx, game)

    for name, data in ALL_PARTS.items():
        addr = part_vis_addr(game, data)
        try:
            read = dme.read_byte(addr)
        except Exception:
            continue

        # Normal direction: collected in-game -> send the check to the server.
        if read == data.collected_byte and data.ap_id not in ctx.checked_locations:
            ctx.locations_checked.add(data.ap_id)
            await ctx.check_locations([data.ap_id])

        # Reverse direction: the location is checked server-side (e.g. !collect,
        # release) but the part was not collected in-game. The pellet is already
        # despawned above; the "collected" byte (UfoParts.mPartVisType = Visible)
        # is only written out of level by sync_server_collected_parts().
        # Here: only the hint.
        elif data.ap_id in ctx.checked_locations and read != data.collected_byte:
            if hint_mode in (2, 3):
                await _create_super_radar_hint(ctx, name)


# PlayerState.mUfoParts (_178, UfoParts*, indexed by the UfoPartIndex enum =
# ALL_PARTS order); UfoParts is 0xE0 bytes, mPartVisType at _DC.
PLAYERSTATE_UFOPARTS = 0x178
UFOPARTS_STRIDE = 0xE0
UFOPART_VISTYPE_OFF = 0xDC
_PART_INDEX = {data.ap_id: i for i, data in enumerate(ALL_PARTS.values())}


def part_vis_addr(game: Game, data) -> int:
    """Address of the part's UfoParts.mPartVisType (the "collected" byte).

    Resolved via playerState->mUfoParts rather than the hardcoded heap address
    from P1Data. Falls back to the hardcoded address if the chain fails.
    """
    ptr = SYM_PLAYER_STATE_PTR.get(game)
    idx = _PART_INDEX.get(data.ap_id)
    if ptr is not None and idx is not None:
        try:
            ps = struct.unpack(">I", dme.read_bytes(ptr, 4))[0]
            if _RAM_MIN <= ps < _RAM_MAX:
                ufo = struct.unpack(">I", dme.read_bytes(ps + PLAYERSTATE_UFOPARTS, 4))[0]
                if _RAM_MIN <= ufo < _RAM_MAX:
                    return ufo + idx * UFOPARTS_STRIDE + UFOPART_VISTYPE_OFF
        except Exception:
            pass
    return data.memory_address[game]


def _ufo_part_drawable(vis_addr: int) -> bool:
    """UfoParts loaded and drawable: mRepairAnimJointIndex (_04) != -1 and
    mPelletShape (_D4) valid. Otherwise showing / animating it would crash
    renderParts() or startUfoPartsMotion() (null shape pointer)."""
    part = vis_addr - UFOPART_VISTYPE_OFF
    try:
        joint = struct.unpack(">i", dme.read_bytes(part + 0x04, 4))[0]
        shape = struct.unpack(">I", dme.read_bytes(part + 0xD4, 4))[0]
    except Exception:
        return False
    return joint != -1 and _RAM_MIN <= shape < _RAM_MAX


def _clear_part_anim_mailbox(ctx) -> None:
    mailbox = getattr(ctx, "part_anim_mailbox", None)
    if mailbox is None:
        return
    try:
        if dme.read_bytes(mailbox, 4) != b"\x00\x00\x00\x00":
            dme.write_bytes(mailbox, b"\x00\x00\x00\x00")
    except Exception:
        pass


async def sync_server_collected_parts(ctx: P1Context, game: Game) -> None:
    """Show server-checked parts on the S.S. Dolphin.

    ShipPartData's "collected" byte is PlayerState::UfoParts.mPartVisType.
    With a recently patched ISO (mailbox), the part is shown right away and the
    game runs its own final animation. Otherwise, setting it to Visible mid-day
    would show the part without its animation started (getUfoParts /
    ufoAssignStart never called), so it is only written out of level (world
    map, menus): at the next day start PlayerState::startAfterMotions() places
    the part correctly.
    """
    in_level = _oneplayer_subsection(game) == ONEPLAYER_NEW_PIKI_GAME
    mailbox = getattr(ctx, "part_anim_mailbox", None)
    if in_level:
        # In a day: only with the ISO patch mailbox, one part at a time (the
        # game clears it after starting the animation), and only during active
        # gameplay: on Olimar's death / day end, PlayerState::exitCourse()
        # resets mPelletShape to nullptr and startUfoPartsMotion() would read
        # 0x28(nullptr).
        if mailbox is None or not is_day_active(game):
            return
        try:
            if dme.read_bytes(mailbox, 4) != b"\x00\x00\x00\x00":
                return
        except Exception:
            return
    for name, data in ALL_PARTS.items():
        if data.ap_id not in ctx.checked_locations:
            continue
        addr = part_vis_addr(game, data)
        try:
            if dme.read_byte(addr) == data.collected_byte:
                continue
            if in_level and not _ufo_part_drawable(addr):
                continue  # part not (yet) loaded on the ship: later
            dme.write_byte(addr, data.collected_byte)
            if ctx.debug_hint:
                logger.info(f"[DEBUG] Part {name} auto-collected (checked server-side)")
            if in_level:
                # The game stub will call startUfoPartsMotion(id, After, false).
                dme.write_bytes(mailbox, PART_MODEL_ID[name])
                return
        except Exception:
            continue


async def handle_pikmin_locations(ctx: P1Context, game: Game):
    """Handle Pikmin collection location checking"""
    try:
        if game not in PIKMIN_ADDRESSES:
            return

        addresses = PIKMIN_ADDRESSES[game]

        # Read current Pikmin counts
        red_count    = dme.read_byte(addresses["red"])
        yellow_count = dme.read_byte(addresses["yellow"])
        blue_count   = dme.read_byte(addresses["blue"])

        # Only act if counts have changed since last tick
        if (red_count == ctx.last_red_count
                and yellow_count == ctx.last_yellow_count
                and blue_count == ctx.last_blue_count):
            return

        ctx.last_red_count    = red_count
        ctx.last_yellow_count = yellow_count
        ctx.last_blue_count   = blue_count

        current_counts = {
            "red":    red_count,
            "yellow": yellow_count,
            "blue":   blue_count,
        }

        # Build reverse map once: ap_id -> (color, threshold)
        id_to_pikmin: dict[int, tuple[str, int]] = {}
        for loc_name, loc_id in PIKMIN_LOCATIONS_MAP.items():
            parts = loc_name.split(" Pikmin: ")
            if len(parts) == 2:
                id_to_pikmin[loc_id] = (parts[0].lower(), int(parts[1]))

        locations_to_check = []

        for loc_id in ctx.missing_locations:
            if loc_id not in id_to_pikmin:
                continue
            color, threshold = id_to_pikmin[loc_id]
            if current_counts[color] >= threshold:
                locations_to_check.append(loc_id)

        if locations_to_check:
            await ctx.check_locations(locations_to_check)

        ctx.pikmin_counts["red"]    = red_count
        ctx.pikmin_counts["yellow"] = yellow_count
        ctx.pikmin_counts["blue"]   = blue_count

    except Exception as e:
        logger.debug(f"Error handling Pikmin locations: {e}")


# ---------------------------------------------------------------------------
# In-place refresh of the world map (story mode).
#
# Offsets verified against the projectPiki/pikmin decomp:
#   src/plugPikiColin/mapSelect.cpp       -> static zen::DrawWorldMap* mapWindow
#   include/zen/DrawWorldMap.h            -> DrawWorldMap offsets
#   src/plugPikiYamashita/drawWorldMap.cpp-> WorldMapCoursePointMgr / CoursePoint
#
# The map freezes area visibility and the part counter when it opens
# (DrawWorldMap constructor; WorldMapCoursePointMgr::init reads courseOpen()).
# Nothing re-evaluates them while the map stays open, so a part/area received
# meanwhile leaves the area hidden and the counter stale.
#
# Fixed without a DOL patch, through the static mapWindow:
#   - counter: mCurrentPartsNum is re-read every frame by a NumberPicCallBack,
#     so rewriting it updates the counter immediately;
#   - areas: for an unlocked area whose course point is not visible yet, set
#     mIsVisible = 1 (selectable) and trigger the reveal animation
#     (mMode=Appear + point.mAppearState=RocketIncoming), like the game does on
#     a real unlock (DrawWorldMap::start -> appear()).
# Addresses/offsets: see SYM_MAP_WINDOW_PTR / MAP_GAME2SCR / WORLDMAP_CHAIN in
# P1Symbols.py (generated by gen_symbols.py from the decomp).
# WorldMapCoursePoint.mLinkPoints (_2C), indexed by linkFlag
# (src/plugPikiYamashita/drawWorldMap.cpp: Up 0, Down 1, Left 2, Right 3).
CP_LINKPOINTS = 0x2C
# DrawWorldMap.mTotalPikiCounts[3] (Blue, Red, Yellow).
DWM_PIKI_COUNTS = 0x44


# Cursor links when ALL areas are open (screen index), taken from
# WorldMapCoursePointMgr::init (courseOpen(Distant Spring) branch).
# scr: 0 Distant Spring, 1 Forest of Hope, 2 Impact Site, 3 Forest Navel,
# 4 Final Trial. Link order: Up, Down, Left, Right.
WORLDMAP_FULL_LINKS = (
    (4, 1, None, 3),       # 0 Distant Spring
    (0, None, None, 2),    # 1 Forest of Hope
    (3, None, 1, None),    # 2 Impact Site
    (4, 2, 0, None),       # 3 Forest Navel
    (None, 3, 0, None),    # 4 Final Trial
)


# Game variant when Distant Spring (scr 0) is closed: Forest of Hope goes up
# to Forest Navel and Forest Navel goes left to Forest of Hope.
WORLDMAP_DS_CLOSED_LINKS = (
    WORLDMAP_FULL_LINKS[0],
    (3, None, None, 2),
    WORLDMAP_FULL_LINKS[2],
    (4, 2, 1, None),
    WORLDMAP_FULL_LINKS[4],
)
def _worldmap_reach_from(links, open_pts: set, start: int) -> set:
    seen, stack = {start}, [start]
    while stack:
        cur = stack.pop()
        for t in links[cur]:
            if t is not None and t in open_pts and t not in seen:
                seen.add(t)
                stack.append(t)
    return seen


def _worldmap_nearest_open(p: int, t: int, open_pts: set):
    """Nearest open area beyond t (t closed), walking through closed areas of the full map."""
    seen, queue = {p, t}, [t]
    while queue:
        cur = queue.pop(0)
        for n in WORLDMAP_FULL_LINKS[cur]:
            if n is None or n in seen:
                continue
            if n in open_pts:
                return n
            seen.add(n)
            queue.append(n)
    return None


def compute_worldmap_links(open_pts: set) -> list:
    """Cursor links for an arbitrary set of open areas.

    1. Base = the game's own table (variant depends on Distant Spring being
       open), so the original cases are unchanged.
    2. While an open area cannot reach another open area (unusual unlock
       order, e.g. Impact Site + Distant Spring), a direction leading to a
       CLOSED area is redirected to the nearest open area beyond it. Valid
       links are never touched.
    """
    base = WORLDMAP_FULL_LINKS if 0 in open_pts else WORLDMAP_DS_CLOSED_LINKS
    links = [list(row) for row in base]
    for _ in range(len(links) * 4):
        changed = False
        for p in sorted(open_pts):
            reach = _worldmap_reach_from(links, open_pts, p)
            if reach >= open_pts:
                continue
            for d in range(4):
                t = links[p][d]
                if t is None or t in open_pts:
                    continue
                n = _worldmap_nearest_open(p, t, open_pts)
                if n is not None and n not in reach:
                    links[p][d] = n
                    changed = True
                    break
        if not changed:
            break
    return links


def _relink_worldmap(wm: int) -> None:
    """Rewrite mLinkPoints of the 5 areas according to the visible areas."""
    W = WORLDMAP_CHAIN
    mgr = struct.unpack(">I", dme.read_bytes(wm + W["DWM_COURSEPOINTMGR"], 4))[0]
    if not (_RAM_MIN <= mgr < _RAM_MAX):
        return
    pts = mgr + W["CPM_POINTS"]
    n = len(WORLDMAP_FULL_LINKS)
    open_pts = {i for i in range(n) if dme.read_byte(pts + i * W["CP_STRIDE"] + W["CP_ISVISIBLE"])}
    for p, row in enumerate(compute_worldmap_links(open_pts)):
        if p not in open_pts:
            continue
        base = pts + p * W["CP_STRIDE"] + CP_LINKPOINTS
        want = b"".join(struct.pack(">I", 0 if t is None else pts + t * W["CP_STRIDE"]) for t in row)
        if dme.read_bytes(base, 16) != want:
            dme.write_bytes(base, want)


def _refresh_worldmap_screen(ctx: P1Context, game: Game, ship_parts_count: int) -> None:
    """Refresh the world map in place when a part/area arrives while the player
    is already on it. No effect outside the world map."""
    ptr_addr = SYM_MAP_WINDOW_PTR.get(game)
    if ptr_addr is None:
        return
    # Only on the world map: mapWindow (a static never reset to zero) may
    # otherwise point to a freed object.
    if _oneplayer_subsection(game) != ONEPLAYER_MAP_SELECT:
        return
    try:
        wm = struct.unpack(">I", dme.read_bytes(ptr_addr, 4))[0]
    except Exception:
        return
    if not (_RAM_MIN <= wm < _RAM_MAX):
        return  # no world map (challenge mode, or not built yet)

    W = WORLDMAP_CHAIN
    try:
        # --- part counter (bottom-left): re-read every frame ---
        cur_addr = wm + W["DWM_CURRPARTS"]
        if struct.unpack(">i", dme.read_bytes(cur_addr, 4))[0] != ship_parts_count:
            dme.write_bytes(cur_addr, struct.pack(">i", ship_parts_count))

        # --- per-colour Pikmin counters (top of the map) ----------
        # DrawWorldMap.mTotalPikiCounts[Blue/Red/Yellow] (_44) is filled once
        # when the map opens (PlayerState::getTotalPikiCount = pikiInfMgr,
        # total over all stages) but re-read every frame by the display.
        # Recompute it from the STAGE counters (where bonuses land).
        stage_addrs = ONION_STAGE_ADDRS_CLIENT.get(game, {})
        for color, idx in (("blue", 0), ("red", 1), ("yellow", 2)):
            stages = stage_addrs.get(color)
            if not stages:
                continue
            total = sum(struct.unpack(">i", dme.read_bytes(a, 4))[0] for a in stages.values())
            cnt_addr = wm + DWM_PIKI_COUNTS + idx * 4
            if struct.unpack(">i", dme.read_bytes(cnt_addr, 4))[0] != total:
                dme.write_bytes(cnt_addr, struct.pack(">i", total))

        # --- cursor navigation links ---------------------------
        # WorldMapCoursePointMgr::init() computes the up/down/left/right links
        # ONCE, when the map opens, and only handles one case: Distant Spring
        # open or not. An area revealed live would be unreachable by the
        # cursor, and a mixed unlock order (e.g. only Impact Site + Distant
        # Spring) would not be navigable at all. So the links are recomputed
        # from the ACTUALLY visible areas (mIsVisible), whatever the unlock order.
        _relink_worldmap(wm)

        # --- areas: only reveal when the map is in Operation (idle) mode,
        #     so a confirmation dialog / the journal is not disturbed.
        if struct.unpack(">i", dme.read_bytes(wm + W["DWM_CURRENTMODE"], 4))[0] != DWM_MODE_OPERATION:
            return
        mgr = struct.unpack(">I", dme.read_bytes(wm + W["DWM_COURSEPOINTMGR"], 4))[0]
        if not (_RAM_MIN <= mgr < _RAM_MAX):
            return

        # Same thresholds as the UNLOCKED_AREAS bits above.
        unlocked = (
            True,                    # 0 Impact Site
            ship_parts_count >= 1,   # 1 Forest of Hope
            ship_parts_count >= 5,   # 2 Forest Navel
            ship_parts_count >= 12,  # 3 Distant Spring
            ship_parts_count >= 29,  # 4 Final Trial
        )
        triggered = False
        for game_area, is_unlocked in enumerate(unlocked):
            if not is_unlocked:
                continue
            point = mgr + W["CPM_POINTS"] + MAP_GAME2SCR[game_area] * W["CP_STRIDE"]
            try:
                if dme.read_byte(point + W["CP_ISVISIBLE"]):
                    continue  # already visible -> idempotent
            except Exception:
                continue
            # Make selectable + play the reveal animation.
            dme.write_byte(point + W["CP_ISVISIBLE"], 1)
            dme.write_bytes(point + W["CP_APPEARSTATE"], struct.pack(">i", CP_APPEAR_START))
            dme.write_bytes(point + W["CP_APPEARTIMER"], struct.pack(">f", 0.0))
            triggered = True
            if getattr(ctx, "debug_hint", False):
                logger.info(f"[DEBUG] Map: area {game_area} revealed in place "
                            f"(scr={MAP_GAME2SCR[game_area]})")
        if triggered:
            dme.write_bytes(mgr + W["CPM_MODE"], struct.pack(">i", CPM_MODE_APPEAR))
    except Exception as e:
        logger.debug(f"[Pikmin] refresh worldmap: {e}")


def _write_playerstate_part_counts(game: Game, total: int, required: int) -> None:
    """Write the low byte of PlayerState.mCurrParts (_17C) and
    mRequiredUfoPartCount (_180) through the playerState pointer."""
    ptr = SYM_PLAYER_STATE_PTR.get(game)
    if ptr is None:
        return
    try:
        ps = struct.unpack(">I", dme.read_bytes(ptr, 4))[0]
        if not (_RAM_MIN <= ps < _RAM_MAX):
            return
        for off, val in ((PLAYERSTATE_OFFSETS["mCurrParts"] + 3, total),
                         (PLAYERSTATE_OFFSETS["mRequiredUfoPartCount"] + 3, required)):
            if dme.read_byte(ps + off) != val:
                dme.write_byte(ps + off, val)
    except Exception as e:
        logger.debug(f"Error writing part counts: {e}")


def _sync_stage_unlock_anim(game: Game, ap_areas: int, game_areas: int) -> None:
    """Sync the world map area-unlock animation.

    gameflow.mPendingStageUnlockID (-1 = none) is set by
    PlayState::openStage(): when Olimar picks up a part IN-GAME (an AP check),
    PlayerState::registerPart() unlocks Forest of Hope (>= 1 part) and
    schedules its animation. Even if the client then resets the areas to the
    AP state, DrawWorldMap::start() makes the animated area APPEAR and puts the
    cursor there, making Forest of Hope reachable with 0 AP parts.

    - animation targeting an area NOT unlocked by AP -> cancelled (-1);
    - area newly unlocked by AP (bit absent in game) -> schedule the game's
      real animation for the next visit to the map (while on the world map,
      the in-place refresh updates the screen instead).
    """
    addr = SYM_GAMEFLOW.get(game, {}).get("PENDING_STAGE_UNLOCK")
    if addr is None:
        return
    try:
        pending = struct.unpack(">i", dme.read_bytes(addr, 4))[0]
        want = pending
        if pending >= 0 and not (ap_areas >> pending) & 1:
            want = -1
        new_bits = ap_areas & ~game_areas & 0b11110  # Impact Site (bit 0) excluded
        if new_bits and _oneplayer_subsection(game) != ONEPLAYER_MAP_SELECT:
            want = new_bits.bit_length() - 1  # most advanced area
        if want != pending:
            dme.write_bytes(addr, struct.pack(">i", want))
    except Exception as e:
        logger.debug(f"Error syncing stage unlock anim: {e}")


def is_final_ending(game: Game) -> bool:
    """True during the ending sequence (end of the last day with 30 parts:
    liftoff, onions, Olimar in space). The game reinitialises the Teki/Movie
    heaps for the cutscenes; the client must not write anything then."""
    if _oneplayer_subsection(game) != ONEPLAYER_NEW_PIKI_GAME or is_day_active(game):
        return False
    ptr = SYM_PLAYER_STATE_PTR.get(game)
    if ptr is None:
        return False
    try:
        ps = struct.unpack(">I", dme.read_bytes(ptr, 4))[0]
        if not (_RAM_MIN <= ps < _RAM_MAX):
            return False
        return struct.unpack(">i", dme.read_bytes(ps + PLAYERSTATE_OFFSETS["mCurrParts"], 4))[0] >= 30
    except Exception:
        return False


async def handle_areas(ctx: P1Context, game: Game):
    # Build set of valid ship part IDs for fast lookup
    ship_part_ids = {data.ap_id for data in ALL_PARTS.values()}

    # Count only real ship parts received
    ship_parts_count = sum(1 for item in ctx.items_received if item.item in ship_part_ids)

    total_required = 0

    if ship_parts_count >= 30:
        total_required = 25

        if not ctx.finished_game:
            await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            ctx.finished_game = True

    areas = 0b00001
    if ship_parts_count >= 1:
        areas += 0b00010
    if ship_parts_count >= 5:
        areas += 0b00100
    if ship_parts_count >= 12:
        areas += 0b01000
    if ship_parts_count >= 29:
        areas += 0b10000

    # mCurrParts / mRequiredUfoPartCount are written through the playerState
    # pointer, and only when the value changes.
    _write_playerstate_part_counts(game, ship_parts_count, total_required)
    game_areas = dme.read_byte(UNLOCKED_AREAS[game])
    _sync_stage_unlock_anim(game, areas, game_areas)
    if game_areas != areas:
        dme.write_byte(UNLOCKED_AREAS[game], areas)

    # Visual stage of the S.S. Dolphin. The game only recomputes
    # mShipUpgradeLevel inside PlayerState::registerPart(), never from the
    # part count; AP checks bypass that function (parts are marked collected
    # directly in memory), so the ship stage must be set here.
    # Same thresholds as the game (see the area unlocks above).
    if ship_parts_count >= 30:
        ship_upgrade_level = 5   # PERFECT
    elif ship_parts_count >= 29:
        ship_upgrade_level = 4
    elif ship_parts_count >= 12:
        ship_upgrade_level = 3
    elif ship_parts_count >= 5:
        ship_upgrade_level = 2
    elif ship_parts_count >= 1:
        ship_upgrade_level = 1
    else:
        ship_upgrade_level = 0

    ps_ptr = SYM_PLAYER_STATE_PTR.get(game)
    if ps_ptr is not None:
        try:
            ps = struct.unpack(">I", dme.read_bytes(ps_ptr, 4))[0]
            if _RAM_MIN <= ps < _RAM_MAX:
                addr = ps + PLAYERSTATE_OFFSETS["mShipUpgradeLevel"]
                # Never decreasing: do not downgrade the visual if
                # ship_parts_count drops for a tick.
                if dme.read_byte(addr) < ship_upgrade_level:
                    dme.write_byte(addr, ship_upgrade_level)
        except Exception as e:
            logger.debug(f"Error writing mShipUpgradeLevel: {e}")

    # If already on the world map, refresh unlocked areas and the part counter
    # without having to leave/restart a day.
    _refresh_worldmap_screen(ctx, game, ship_parts_count)


async def handle_day_cycle(ctx: P1Context, game: Game) -> None:
    """Manage the day counter based on the player's day cycle option."""
    slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
    mode  = slot_data.get("day_cycle_mode",  0)  # 0=normal, 1=custom_range, 2=fixed
    d_min = slot_data.get("day_cycle_min",   2)
    d_max = slot_data.get("day_cycle_max",  29)
    fixed = slot_data.get("day_cycle_fixed",  2)

    try:
        day = dme.read_byte(DAY_NUMBER[game])
    except Exception:
        return

    if day == 0:
        return  # Player is on the main menu, not in-game yet

    if ctx.debug_days:
        import time as _time
        _now = _time.monotonic()
        if _now - ctx._last_day_debug_log >= 60.0:
            logger.info(f"[DEBUG] Day cycle: day={day} mode={mode}")
            ctx._last_day_debug_log = _now

    new_day = day

    if mode == 0:  # normal: force 2 if day is 1 or above 29
        if day == 1 or day > 29:
            new_day = 2

    elif mode == 1:  # custom range
        low  = max(2, min(d_min, d_max))
        high = max(low, d_max)
        if day < low:
            new_day = low
        elif day > high:
            new_day = low

    elif mode == 2:  # fixed — lock on fixed value
        new_day = max(2, min(fixed, 29))

    if new_day != day:
        try:
            dme.write_byte(DAY_NUMBER[game], new_day)
        except Exception:
            pass


async def handle_qol_first_day(ctx: P1Context, game: Game) -> None:
    """QOL 'Normal First Day': clear PlayerState.mIsTutorialMode.

    While this flag is 1, the game treats day 1 as a tutorial: crash intro
    (DEMOID_OlimarWakeUp instead of the normal landing), frozen clock and
    scripted pop-ups. Forcing it to 0 once a save is loaded makes day 1
    behave normally. Day 1 loads the level without going through the world
    map, so it is cleared every tick (very early) and kept corrected even if
    the intro played before our first tick.
    """
    slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
    if not slot_data.get("normal_first_day", 1):
        return

    ptr = SYM_PLAYER_STATE_PTR.get(game)
    if ptr is None:
        return
    try:
        ps = struct.unpack(">I", dme.read_bytes(ptr, 4))[0]
    except Exception:
        return
    if not (_RAM_MIN <= ps < _RAM_MAX):
        return

    addr = ps + PLAYERSTATE_OFFSETS["mIsTutorialMode"]
    try:
        if dme.read_byte(addr) != 0:
            dme.write_byte(addr, 0)
    except Exception:
        pass


def _set_demo_flags(stored: int, indices) -> None:
    """Mark a list of EDemoFlags indices as already seen in the RAM bitset."""
    for idx in indices:
        byte_addr = stored + (idx >> 3)
        cur = dme.read_byte(byte_addr)
        bit = 1 << (idx & 7)
        if not (cur & bit):
            dme.write_byte(byte_addr, cur | bit)


async def handle_qol_skip_cutscenes(ctx: P1Context, game: Game) -> None:
    """QOL: skip the cutscenes/texts listed in the 'skip_events' OptionSet by
    marking their DemoFlags as already seen (mStoredFlags = u8[32] pointed to by
    PlayerState+0x5C; bit of flag i = mStoredFlags[i>>3] & (1 << (i & 7))).

    Special case "Onion Discovery": skipping the discovery also deprives the
    game of the onion's activation (boot) and registration (tracking + display).
    This is repaired via mContainerFlag + mDisplayPikiFlag:
      * boot bits (y) set for all colours (onion active at spawn);
      * tracking bit (x) + display bit set for the onion Olimar actually
        reached (navi->mGoalItem), not merely for entering the area.
    ("Part Collection" and "Ship Upgrade" are DOL patches, applied at patch time.)
    """
    slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
    skips = set(slot_data.get("skip_events", []))
    if not skips:
        return

    ptr = SYM_PLAYER_STATE_PTR.get(game)
    if ptr is None:
        return
    try:
        ps = struct.unpack(">I", dme.read_bytes(ptr, 4))[0]
        if not (_RAM_MIN <= ps < _RAM_MAX):
            return
        stored = struct.unpack(">I", dme.read_bytes(ps + PLAYERSTATE_OFFSETS["mDemoFlagsStoredPtr"], 4))[0]
        if not (_RAM_MIN <= stored < _RAM_MAX):
            return

        # Pre-mark the DemoFlags of all selected entries.
        flags = []
        for key in skips:
            flags.extend(SKIP_EVENT_DEMOFLAGS.get(key, ()))
        if flags:
            _set_demo_flags(stored, flags)

        # Onion repair (tracking + display) if its discovery is skipped.
        if "Onion Discovery" in skips:
            cf_addr = ps + PLAYERSTATE_OFFSETS["mContainerFlag"]
            cf = dme.read_byte(cf_addr)
            new_cf = cf | CONTAINER_BOOT_ALL
            if (new_cf & 0x07) != 0x07:  # a tracking bit is still missing
                navi = _resolve_olimar(game)
                if navi:
                    goal = struct.unpack(">I", dme.read_bytes(navi + NAVI_CHAIN["NAVI_GOALITEM"], 4))[0]
                    # Only set hasContainer if mGoalItem really points to a live
                    # onion (mObjType == OBJTYPE_Goal). A stale pointer would give
                    # a wrong colour -> hasContainer for a colour with no onion
                    # present -> null->refresh() at end of day (onion liftoff
                    # cutscene) -> crash.
                    if _RAM_MIN <= goal < _RAM_MAX:
                        objtype = int.from_bytes(
                            dme.read_bytes(goal + ONION_CHAIN["CREATURE_OBJTYPE"], 4), "big", signed=True
                        )
                        if objtype == OBJTYPE_GOAL:
                            colour = int.from_bytes(dme.read_bytes(goal + ONION_CHAIN["GOAL_COLOUR"], 2), "big")
                            name = COLOR_BY_INDEX.get(colour)
                            if name:
                                new_cf |= CONTAINER_COLOR_BIT.get(name, 0)
            if new_cf != cf:
                dme.write_byte(cf_addr, new_cf)

            # mDisplayPikiFlag must cover the same colours as tracking (x),
            # otherwise owned onions/counters are missing on the world map and
            # the end-of-day summary. Identical bits (1 << colour).
            owned = new_cf & 0x07
            df_addr = ps + PLAYERSTATE_OFFSETS["mDisplayPikiFlag"]
            df = dme.read_byte(df_addr)
            if (df | owned) != df:
                dme.write_byte(df_addr, df | owned)
    except Exception:
        pass


# --- Onion light beam (cone) ---------------------------------------------------
# GoalItem (include/GoalItem.h):
#   _3F6 bool mIsClosing         _3F8 f32 mConeSizeTimer
#   _3FC Vector3f full cone scale
#   _408 bool mIsConeEmit        _40C EffShpInst* mSpotModelEff (mSRT.s @ +0x14)
# An undiscovered onion is loaded with a cone (and reference scale) of 0; only
# the discovery cutscene makes it appear. With "Onion Discovery" skipped, the
# beam would therefore be missing until the next day.
GOAL_IS_CLOSING = 0x3F6
GOAL_CONE_TIMER = 0x3F8
GOAL_CONE_FULL_SCALE = 0x3FC
GOAL_IS_CONE_EMIT = 0x408
GOAL_SPOT_MODEL_EFF = 0x40C
EFFSHPINST_SCALE = 0x14
_BOOT_BIT = {"blue": 0x08, "red": 0x10, "yellow": 0x20}  # hasBootContainer (y)
CONE_DEFAULT_SCALE = 0.1   # full cone scale observed on all onions
CONE_MAX_TRIES = 5         # max fixes per onion per day
CONE_START_DELAY = 2.0     # seconds of free gameplay before touching cones
MOVIE_IS_ACTIVE = 0x124    # MoviePlayer.mIsActive (bool)


def is_movie_playing(game: Game) -> bool:
    """Return True if a cutscene (MoviePlayer) is currently playing."""
    gf = SYM_GAMEFLOW.get(game)
    if not gf or "MOVIE_PLAYER_PTR" not in gf:
        return False
    try:
        mp = struct.unpack(">I", dme.read_bytes(gf["MOVIE_PLAYER_PTR"], 4))[0]
        if not (_RAM_MIN <= mp < _RAM_MAX):
            return False
        return dme.read_byte(mp + MOVIE_IS_ACTIVE) != 0
    except Exception:
        return False


async def handle_onion_cone(ctx: P1Context, game: Game) -> None:
    """With "Onion Discovery" skipped, force the beam of all present onions from the start of the day.

    A cone at 0 gets the scale of a normal onion (else 0.1), written directly
    into its model (no startConeEmit: it would force an undiscovered onion's AI
    into GOAL_Wait). The game may shrink the cone again right after loading, so
    it is re-checked every tick, at most CONE_MAX_TRIES times.
    """
    slot_data = getattr(ctx, "slot_data", None) or {}
    if "Onion Discovery" not in slot_data.get("skip_events", []):
        return
    # Not during the start-of-day cutscene (onion landing, which opens the cones
    # itself) nor under a menu; then wait CONE_START_DELAY seconds of free
    # gameplay, otherwise the beam would appear before the cutscene ends.
    if is_movie_playing(game) or is_overlay_active(game):
        ctx._cone_free_since = None
        return
    now = time.monotonic()
    if ctx._cone_free_since is None:
        ctx._cone_free_since = now
    if now - ctx._cone_free_since < CONE_START_DELAY:
        return
    ps_ptr = SYM_PLAYER_STATE_PTR.get(game)
    if ps_ptr is None:
        return
    try:
        ps = struct.unpack(">I", dme.read_bytes(ps_ptr, 4))[0]
        if not (_RAM_MIN <= ps < _RAM_MAX):
            return
        cf = dme.read_byte(ps + PLAYERSTATE_OFFSETS["mContainerFlag"])
    except Exception:
        return
    todo = [c for c, bit in _BOOT_BIT.items() if cf & bit and c not in ctx._cone_ok]
    if not todo:
        return
    onions = find_onion_containers(game)

    def f32(addr: int) -> float:
        return struct.unpack(">f", dme.read_bytes(addr, 4))[0]

    # Reference scale: that of an onion whose cone is normal.
    ref = CONE_DEFAULT_SCALE
    for g in onions.values():
        try:
            if f32(g + GOAL_CONE_FULL_SCALE) > 0.0:
                ref = f32(g + GOAL_CONE_FULL_SCALE)
                break
        except Exception:
            pass
    full = struct.pack(">fff", ref, ref, ref)

    for color in todo:
        goal = onions.get(color)
        if not goal:
            continue  # onion not present in this area
        try:
            if dme.read_byte(goal + GOAL_IS_CONE_EMIT) or dme.read_byte(goal + GOAL_IS_CLOSING):
                continue  # game animation in progress
            eff = struct.unpack(">I", dme.read_bytes(goal + GOAL_SPOT_MODEL_EFF, 4))[0]
            if not (_RAM_MIN <= eff < _RAM_MAX):
                continue
            if f32(eff + EFFSHPINST_SCALE) > 0.0:
                continue  # currently visible: will re-check
            tries = ctx._cone_tries.get(color, 0)
            if tries >= CONE_MAX_TRIES:
                ctx._cone_ok.add(color)
                if ctx.debug_pbonus:
                    logger.info(f"[DEBUG] {color} onion cone: {CONE_MAX_TRIES} tries, giving up.")
                continue
            ctx._cone_tries[color] = tries + 1
            if f32(goal + GOAL_CONE_FULL_SCALE) <= 0.0:
                dme.write_bytes(goal + GOAL_CONE_FULL_SCALE, full)
            dme.write_bytes(eff + EFFSHPINST_SCALE, full)
            if ctx.debug_pbonus:
                logger.info(f"[DEBUG] {color} onion cone re-triggered (scale {ref:.2f}).")
        except Exception as e:
            if ctx.debug_pbonus:
                logger.info(f"[DEBUG] {color} onion cone: error {e!r}")


async def handle_qol_min_leaf(ctx: P1Context, game: Game) -> None:
    """QOL 'Always Keep One Leaf Pikmin': keep at least 1 Leaf Pikmin, ONLY for
    colors actually owned (hasContainer).

    Forcing an unowned color would create ghost Pikmin with no onion, and the
    end-of-day sequence (per-onion fly-away cutscene + results) would crash on
    a null pointer. Also skips the new-sprout cutscene at the start of the day.
    """
    slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
    if not slot_data.get("always_min_one_leaf", 1):
        return

    stage = SYM_ONION_STAGE_ADDRS.get(game)
    if not stage:
        return
    ptr = SYM_PLAYER_STATE_PTR.get(game)
    if ptr is None:
        return
    try:
        ps = struct.unpack(">I", dme.read_bytes(ptr, 4))[0]
        if not (_RAM_MIN <= ps < _RAM_MAX):
            return
        owned = dme.read_byte(ps + PLAYERSTATE_OFFSETS["mContainerFlag"]) & 0x07
    except Exception:
        return

    for color in ("red", "yellow", "blue"):
        if not (owned & CONTAINER_COLOR_BIT.get(color, 0)):
            continue  # color not owned -> no ghost Pikmin
        addr = stage.get(color, {}).get("leaf")
        if addr is None:
            continue
        try:
            cur = struct.unpack(">I", dme.read_bytes(addr, 4))[0]
            if cur == 0:
                dme.write_bytes(addr, struct.pack(">I", 1))
        except Exception:
            pass


async def handle_qol_trip_item(ctx: P1Context, game: Game) -> None:
    """QOL Disable Pikmin Trip in 'item' mode: once the 'Trip Immunity' item is
    received, write 2.0f over the 0.9999f constant used by the trip test.
    getRand returns [0,1[, so the condition is never true and Pikmin never trip.

    This writes DATA (not code): Dolphin's JIT re-reads it on every execution,
    whereas patching code (bne->b) has no effect since Dolphin does not
    recompile an already JIT-ed block. It is re-checked/re-applied every tick
    (cheap) to survive a .sdata2 reload."""
    slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
    if int(slot_data.get("disable_pikmin_trip", 1)) != 2:  # option_item
        return
    if not any(it.item == TRIP_IMMUNITY_ITEM_ID for it in ctx.items_received):
        return

    addr = SYM_TRIP_RAND_CONST.get(game)
    if addr is None:
        return  # version with no known address (NTSC): not applied
    want = struct.pack(">f", TRIP_DISABLED_FLOAT)
    try:
        if dme.read_bytes(addr, 4) != want:
            dme.write_bytes(addr, want)
            if not getattr(ctx, "_trip_ram_patched", False):
                ctx._trip_ram_patched = True
                logger.info(f"[Pikmin] Trip Immunity applied (constant @ 0x{addr:08X}).")
    except Exception:
        pass


def build_hint_bytes(ctx: P1Context, part_name: str, hint_mode: int) -> bytes:
    """Build the hint as raw bytes, using ESC (0x1B) as GC color code prefix."""
    loc_id = ALL_PARTS[part_name].ap_id
    lang = getattr(ctx, "detected_language", "en")
    lab = _labels(lang)
    shown_name = _part_display_name(part_name, lang)

    if hint_mode == 1:  # item mode: show what this location contains
        info = ctx.scouted_locations.get(loc_id)
        if not info:
            return b""
        item_name = info["item_name"]
        player_id = info["player"]
        player_name = ctx.player_names.get(player_id, str(player_id))
        flags = info.get("flags", 0)

        if flags & 0b100:
            item_color = "ff0000ff"
        elif flags & 0b010:
            item_color = "00ffffff"
        elif flags & 0b001:
            item_color = "cc00ffff"
        else:
            item_color = "b4ffffff"

        text = (
            f"\x1BCC[ff0000ff]{shown_name}\x1BCC[b4ffffff]\n"
            f"{lab['contains']} \x1BCC[{item_color}]{item_name}\x1BCC[b4ffffff]\n"
            f"{lab['for']} \x1BCC[ff0000ff]{player_name}\x1BCC[b4ffffff]"
        )
        return _encode_hint(text)

    elif hint_mode == 2:  # super radar mode
        slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
        hints = slot_data.get("hints", {})
        hint_data = hints.get(part_name)

        if ctx.debug_hint:
            logger.info(f"[DEBUG] Super Radar - part: {part_name}, hints count: {len(hints)}, hint_data: {hint_data}")

        if hint_data:
            item_name   = hint_data.get("Item", "Unknown")
            location    = hint_data.get("Location", "Unknown")
            send_player = hint_data.get("Send Player", "Unknown")
            hint_class  = hint_data.get("Class", "Other")

            if ctx.debug_hint:
                logger.info(f"[DEBUG] Super Radar - Item: {item_name}, Location: {location}, SendPlayer: {send_player}, Class: {hint_class}")

            if hint_class == "Prog":
                item_color = "cc00ffff"
            elif hint_class == "Trap":
                item_color = "ff0000ff"
            else:
                item_color = "00ffffff"

            text = (
                f"\x1BCC[ff0000ff]{shown_name}\x1BCC[b4ffffff]\n"
                f"{lab['at']} \x1BCC[ff0000ff]{location}\x1BCC[b4ffffff] "
                f"{lab['in']} \x1BCC[ff0000ff]{send_player}\x1BCC[b4ffffff]"
            )
        else:
            if ctx.debug_hint:
                logger.info(f"[DEBUG] Super Radar - No hint data found for {part_name}")
            text = (
                f"\x1BCC[cc00ff]{shown_name}\x1BCC[b4ffffff]\n"
                f"\x1BCC[00ffffff]{lab['none']}"
            )

        return _encode_hint(text)

    elif hint_mode == 3:  # both mode: show item content AND super radar info
        slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
        hints = slot_data.get("hints", {})
        radar_hint_key = f"{part_name}_radar"

        info = ctx.scouted_locations.get(loc_id)
        radar_hint_data = hints.get(radar_hint_key)
        if not radar_hint_data:
            radar_hint_data = hints.get(part_name)

        if not info or not radar_hint_data:
            if ctx.debug_hint:
                logger.info(f"[DEBUG] Both - Missing data: info={bool(info)}, radar_hint_data={bool(radar_hint_data)}")
            return b""

        item_name   = info["item_name"]
        player_id   = info["player"]
        player_name = ctx.player_names.get(player_id, str(player_id))
        flags       = info.get("flags", 0)

        if flags & 0b100:
            item_color = "ff0000ff"
        elif flags & 0b010:
            item_color = "00ffffff"
        elif flags & 0b001:
            item_color = "cc00ffff"
        else:
            item_color = "b4ffffff"

        location    = radar_hint_data.get("Location", "Unknown")
        send_player = radar_hint_data.get("Send Player", "Unknown")

        text = (
            f"\x1BCC[ff0000ff]{shown_name}\x1BCC[b4ffffff]\n"
            f"{lab['contains']} \x1BCC[{item_color}]{item_name}\x1BCC[b4ffffff]\n"
            f"{lab['for']} \x1BCC[ff0000ff]{player_name}\x1BCC[b4ffffff]\n"
            f"\n{lab['at']} :\n\x1BCC[ff0000ff]{location}\x1BCC[b4ffffff]\n"
            f"{lab['in']} \x1BCC[ff0000ff]{send_player}\x1BCC[b4ffffff]"
        )
        if ctx.debug_hint:
            logger.info(f"[DEBUG] Both hint text length: {len(text)}")
        return _encode_hint(text)

    return b""


async def handle_ship_part_hints(ctx: P1Context, game: Game) -> None:
    """Detect which ship part text is displayed and replace it with an Archipelago hint.
    Re-applies the hint every tick as long as the original game text is still visible,
    so the game cannot permanently overwrite our text."""
    slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
    hint_mode = slot_data.get("ship_part_hint_mode", 0)
    if hint_mode == 0:
        return

    hint_mode_is_both = hint_mode == 3

    # Address resolved dynamically every tick: it depends on the current
    # allocation of the text window. PAL and NTSC-U.
    text_addr = resolve_ship_part_text_addr(game)
    if text_addr is None:
        return

    try:
        raw = dme.read_bytes(text_addr, SHIP_PART_TEXT_LENGTH)
    except Exception:
        return

    if not any(raw):
        ctx.last_hint_shown = ""
        ctx.last_hint_bytes = b""
        return

    # Which part is displayed? Read gameflow.mShipTextPartID (s16), a STATIC
    # symbol present in both PAL and NTSC, rather than matching the part name in
    # the text itself (which depends on the language and disappears once our
    # own text is written).
    detected_part = read_displayed_part(game)
    if detected_part is None:
        return

    if detected_part != ctx.last_hint_shown:
        loc_id = ALL_PARTS[detected_part].ap_id
        ctx.hint_both_toggle = False
        ctx.hint_both_last_toggle = time.monotonic()

        if hint_mode == 1 or hint_mode_is_both:
            item_hint_key = f"{detected_part}_item" if hint_mode_is_both else detected_part
            if item_hint_key not in ctx.created_hints:
                ctx.created_hints.add(item_hint_key)
                await ctx.send_msgs([{
                    "cmd": "CreateHints",
                    "locations": [loc_id],
                    "player": ctx.slot,
                }])
                if ctx.debug_hint:
                    logger.info(f"[DEBUG] CreateHints sent for {detected_part} (loc_id={loc_id})")

        if hint_mode == 2 or hint_mode_is_both:
            slot_hints: dict = (ctx.slot_data or {}).get("hints", {})
            radar_hint_key = f"{detected_part}_radar" if hint_mode_is_both else detected_part
            hint_data = slot_hints.get(radar_hint_key)
            if not hint_data:
                hint_data = slot_hints.get(detected_part)
            if hint_data and radar_hint_key not in ctx.created_hints:
                ctx.created_hints.add(radar_hint_key)
                try:
                    target_loc_id = int(hint_data.get("Location ID", 0))
                    target_player = int(hint_data.get("Send Player ID", ctx.slot))
                except (ValueError, TypeError):
                    target_loc_id = 0
                    target_player = ctx.slot
                if target_loc_id:
                    await ctx.send_msgs([{
                        "cmd": "CreateHints",
                        "locations": [target_loc_id],
                        "player": target_player,
                    }])
                    if ctx.debug_hint:
                        logger.info(f"[DEBUG] Super Radar CreateHints for {detected_part} "
                                    f"(loc_id={target_loc_id}, player={target_player})")

        current_hint_mode = hint_mode
        hint_bytes = build_hint_bytes(ctx, detected_part, current_hint_mode)
        if not hint_bytes:
            if ctx.debug_hint:
                logger.info(f"[DEBUG] No hint text for {detected_part} (scouted={len(ctx.scouted_locations)})")
            return

        ctx.last_hint_shown = detected_part
        ctx.last_hint_bytes = hint_bytes

        if ctx.debug_hint:
            logger.info(f"[DEBUG] Writing hint for {detected_part} (mode={current_hint_mode})")

        try:
            dme.write_bytes(text_addr, hint_bytes)
        except Exception as e:
            logger.debug(f"Error writing hint text: {e}")

    else:
        # Same part still displayed: simply rewrite the same text.
        # Mode 3 shows a single combined text (item + radar) built by
        # build_hint_bytes().
        if ctx.last_hint_bytes:
            try:
                dme.write_bytes(text_addr, ctx.last_hint_bytes)
            except Exception as e:
                logger.debug(f"Error re-applying hint: {e}")
        elif ctx.scouted_locations or ctx.all_locations_scouted:
            hint_bytes = build_hint_bytes(ctx, detected_part, hint_mode)
            if hint_bytes:
                ctx.last_hint_bytes = hint_bytes
                if ctx.debug_hint:
                    logger.info(f"[DEBUG] Late hint build for {detected_part}")
                try:
                    dme.write_bytes(text_addr, hint_bytes)
                except Exception as e:
                    logger.debug(f"Error writing late hint: {e}")


def read_iso_slot_name() -> str:
    """Search game RAM (DOL .text) for the slot-name block written by the patcher
    (P1Rom) and return the name, or "" (older ISO)."""
    from .P1Rom import SLOT_NAME_MAGIC, SLOT_NAME_MAX
    start, end, chunk = 0x80003000, 0x80400000, 0x40000
    overlap = len(SLOT_NAME_MAGIC) + 1 + SLOT_NAME_MAX
    addr = start
    try:
        while addr < end:
            data = dme.read_bytes(addr, min(chunk + overlap, end - addr))
            i = data.find(SLOT_NAME_MAGIC)
            if i >= 0:
                j = i + len(SLOT_NAME_MAGIC)
                length = data[j] if j < len(data) else 0
                raw = data[j + 1:j + 1 + min(length, SLOT_NAME_MAX)]
                return raw.decode("utf-8", "replace").strip("\x00")
            addr += chunk
    except Exception as e:
        logger.debug(f"read_iso_slot_name: {e}")
    return ""


def find_part_anim_mailbox() -> Optional[int]:
    """Return the address of the part-animation mailbox (ISO patch,
    P1Rom.apply_part_anim_patch), or None (ISO patched without it).
    The block lives in a free area of the DOL .init (0x80003100-0x80005600)."""
    from .P1Rom import PART_ANIM_MAGIC
    try:
        data = dme.read_bytes(0x80003000, 0x3000)
    except Exception:
        return None
    i = data.find(PART_ANIM_MAGIC)
    return 0x80003000 + i + len(PART_ANIM_MAGIC) if i >= 0 else None


def find_death_cause_ring() -> Optional[int]:
    """Return the address of the buffer holding Olimar's last received hits.

    The buffer is created by the ISO patch (P1Rom.apply_death_cause_patch).
    Returns None if the ISO was patched without it."""
    from .P1Rom import DEATH_CAUSE_MAGIC
    try:
        data = dme.read_bytes(0x80003000, 0x3000)
    except Exception:
        return None
    i = data.find(DEATH_CAUSE_MAGIC)
    return 0x80003000 + i + len(DEATH_CAUSE_MAGIC) if i >= 0 else None


def _run_in_daemon_thread(func, *args) -> "asyncio.Future":
    """Execute func(*args) in a throwaway daemon thread and return an awaitable.

    loop.run_in_executor(None, ...) uses asyncio's default ThreadPoolExecutor, and
    concurrent.futures registers an atexit hook that joins every thread it spawned,
    even one stuck in a blocked dolphin_memory_engine call (asyncio.wait_for() only
    stops waiting, it does not kill the thread). That could hang the process on exit.
    A plain daemon thread is not tracked by that machinery, so the interpreter kills
    it on exit and the client can close.
    """
    fut: concurrent.futures.Future = concurrent.futures.Future()

    def _target():
        if fut.set_running_or_notify_cancel():
            try:
                result = func(*args)
            except BaseException as e:
                fut.set_exception(e)
            else:
                fut.set_result(result)

    threading.Thread(target=_target, name="PikminDMEWorker", daemon=True).start()
    return asyncio.wrap_future(fut)


async def dolphin_loop(ctx: P1Context):
    game_version = None

    while not ctx.exit_event.is_set():
        try:
            await asyncio.wait_for(ctx.watcher_event.wait(), 1.0)
        except asyncio.TimeoutError:
            pass

        # Do not run a full tick (DME reads, handlers) once shutdown was requested.
        if ctx.exit_event.is_set():
            break

        ctx.watcher_event.clear()

        if ctx.needs_location_scout:
            # Only scout locations that actually exist for this player, as provided
            # by the server (missing | checked). Scouting the hardcoded ALL_LOCATIONS
            # would request locations that were never created and error the server.
            server_locs = list(set(ctx.checked_locations) | set(ctx.missing_locations))
            if server_locs:
                ctx.needs_location_scout = False
                ctx.scout_sent = True
                ctx.scout_sent_time = time.monotonic()
                ctx.scout_received = False
                await ctx.send_msgs([{
                    "cmd": "LocationScouts",
                    "locations": server_locs,
                    "create_as_hint": 0,
                }])
            # If the set is still empty (Connected not fully processed), leave
            # needs_location_scout True to retry on the next tick.

        if ctx.scout_sent and not ctx.scout_received:
            elapsed = time.monotonic() - ctx.scout_sent_time
            if elapsed >= SCOUT_RETRY_INTERVAL:
                ctx.scout_sent_time = time.monotonic()
                server_locs = list(set(ctx.checked_locations) | set(ctx.missing_locations))
                # Debug message, only visible with /debughint
                # (LocationScouts feed the part hints).
                if ctx.debug_hint:
                    logger.info(f"[DEBUG] Retrying LocationScouts (no response after {elapsed:.0f}s, "
                                f"scouted={len(ctx.scouted_locations)})")
                if server_locs:
                    await ctx.send_msgs([{
                        "cmd": "LocationScouts",
                        "locations": server_locs,
                        "create_as_hint": 0,
                    }])

        try:
            # Run blocking DME calls in a throwaway daemon thread with a timeout so
            # that closing Dolphin OR closing the client itself never freezes the
            # process, even if a call stays stuck (see _run_in_daemon_thread).
            def _dme_tick():
                if not dme.is_hooked():
                    dme.hook()
                if not dme.is_hooked():
                    return None
                return dme.read_bytes(0x80000000, 6)

            try:
                game = await asyncio.wait_for(
                    _run_in_daemon_thread(_dme_tick),
                    timeout=3.0
                )
            except asyncio.TimeoutError:
                logger.warning("[Pikmin] Dolphin read timed out — emulator may have closed.")
                ctx.dolphin_status_text = "Disconnected - Emulator closed"
                try:
                    dme.un_hook()
                except Exception:
                    pass
                game_version = None
                continue

            if game is None:
                if dme.memory_override_detected():
                    ctx.dolphin_status_text = ("Disconnected - Hook Failed - "
                                               f"Disable {MEMORY_OVERRIDE_OPTION}")
                    if not ctx._override_warned:
                        ctx._override_warned = True
                        logger.warning(f"Disable {MEMORY_OVERRIDE_OPTION} in Dolphin "
                                       "(Options > Configuration > Advanced), then restart the game.")
                else:
                    ctx.dolphin_status_text = "Disconnected - Hook Failed"
                continue
            ctx._override_warned = False

            # Build expected patched Game ID from slot_data
            slot_data = getattr(ctx, "slot_data", {}) or {}
            suffix = slot_data.get("game_id_suffix", "")

            # A patched ISO no longer has GPIP01/GPIE01: the Game ID prefix tells
            # the original version, hence which memory addresses to use.
            # P1P = PAL, P1E = NTSC-U.
            base_version = BASE_ID_BY_PATCHED_PREFIX.get(game[:3])

            if base_version is None:
                ctx.dolphin_status_text = f"Connected - Wrong Game (patch your ISO first) [{game!r}]"
                continue

            # Patched ISO detected: read the slot name and start the pending connection.
            # Re-read if another patched ISO is launched (different Game ID).
            if game != ctx._detected_game_id:
                ctx._detected_game_id = game
                ctx.iso_slot_name = read_iso_slot_name()
                ctx.part_anim_mailbox = find_part_anim_mailbox()
                ctx.death_cause_ring = find_death_cause_ring()
            if not ctx.game_detected:
                ctx.game_detected = True
                if ctx._pending_connect is not None:
                    address, ctx._pending_connect = ctx._pending_connect, None
                    async_start(ctx.connect(address or None), name="connect")

            if suffix:
                expected_patched_id = game[:3] + suffix.encode("ascii")
                if game != expected_patched_id:
                    ctx.dolphin_status_text = f"Connected - Wrong Game (expected {expected_patched_id.decode()})"
                    continue

            game_version = base_version

            ctx.dolphin_status_text = f"Connected - {game.decode()}"
        except Exception as e:
            logger.error(e)
            logger.info("Trying to reconnect to Dolphin...")
            ctx.dolphin_status_text = "??? - Exception Occured"
            dme.un_hook()
            continue

        # Two gating levels depending on what each handler reads/writes:
        #   in_level    = Olimar is in a level (NewPikiGame)
        #   save_active = level OR world map (level select)
        # On the title screen and save menu, both are false.
        in_level = is_in_level(game_version)
        save_active = is_save_active(game_version)

        # Custom Save: track game loads / saves.
        try:
            track_game_save(ctx, game_version)
        except Exception:
            logger.exception("[Pikmin] Error in track_game_save - the loop continues.")

        # Sync message based on save_active: passing through the world map
        # between levels must not show "paused".
        if save_active != ctx._save_was_loaded:
            lang = getattr(ctx, "detected_language", "en")
            if save_active:
                msg = SYNC_ACTIVE_MSG.get(lang, SYNC_ACTIVE_MSG["en"])
                logger.info(f"[Pikmin] {msg}")
                # Restart cleanly on resume: rescan locations and let
                # handle_pikmin_items re-apply the received bonuses.
                ctx.needs_location_scout = True
            else:
                msg = SYNC_PAUSED_MSG.get(lang, SYNC_PAUSED_MSG["en"])
                logger.info(f"[Pikmin] {msg}")
            ctx._save_was_loaded = save_active

        # Reset DeathLink state at the start of each day: rising edge of "in a
        # level" (entering NewPikiGame). Re-arms the safety lock and restarts
        # counting. Independent of the day cycle (which can freeze DAY_NUMBER)
        # since it relies on actually entering a level.
        if in_level and not ctx._in_level_prev:
            # Initialize _orima_was_dead with the REAL current value, not False:
            # at the very start of the day orimaDead may still be True (left over
            # from the previous death before the game resets it), and forcing False
            # would create a false edge and send a spurious DeathLink.
            ctx._orima_was_dead = read_orima_dead(game_version)
            ctx._dead_pikis_last = None
            ctx._dead_pikis_sent = 0
            ctx._bond_dead_last = None
            ctx._bond_kill_pending = False
            ctx._olimar_bond_last = None
            ctx._cone_ok = set()
            ctx._cone_tries = {}
            ctx._cone_free_since = None
            ctx._suppress_orima_send = False
            ctx._deathlink_locked_this_day = False
            ctx._pending_self_kill = False
            # New day: lift the lock set by an End Day Trap and arm a short grace
            # delay before applying traps again.
            ctx._traps_suspended_until_next_day = False
            ctx._trap_grace_ticks = 0
            ctx._trap_free_since = None  # shared delay with the cones
            ctx._dl_free_since = None    # same for received DeathLink
        ctx._in_level_prev = in_level
        ctx._save_was_loaded_prev_death = save_active

        # Handlers reading level-specific memory (part collection, squad
        # counters, DeathLink): only run inside a level.
        in_level_handlers = (handle_parts, handle_pikmin_locations, handle_pikmin_bond, handle_olimar_bond,
                             handle_onion_cone,
                             handle_population_graph,
                             handle_death_link, handle_traps)
        # Handlers also active on the world map: item reception (persisted via
        # STAGE) and area unlocking (visible on the map).
        save_active_handlers = (handle_pikmin_items, handle_areas, sync_server_collected_parts,
                                handle_tracker_stage,
                                handle_qol_skip_cutscenes,
                                handle_qol_min_leaf)
        # Cosmetic/mechanical handlers: always run (they have internal guards).
        always_handlers = (handle_qol_first_day, handle_qol_trip_item, handle_trip_trap_timer,
                           handle_day_cycle, handle_ship_part_hints)

        # After the goal, GameExit does a softReset then enters SECTION_MovSample
        # (h4m credits). The heap is then reused by the video decoder / GX FIFO,
        # but static pointers (playerState, tutorialWindow...) keep their old
        # value, so writes through them corrupt the GPU stream ("unknown GFX FIFO
        # opcode"). Therefore RAM is only touched in story mode (save menus,
        # intro, map, level).
        story_active = _oneplayer_subsection(game_version) in _STORY_SUBSECTIONS
        # During the ending sequence (takeoff -> space) the game reinitializes its
        # heaps for cutscenes: no writes, only the goal is sent.
        ending = story_active and is_final_ending(game_version)
        if getattr(ctx, "debug_writes", False):
            _state = (_oneplayer_subsection(game_version), is_day_active(game_version), ending)
            if _state != getattr(ctx, "_debug_state", None):
                ctx._debug_state = _state
                logger.info(f"[DEBUG WRITES] subsection={_state[0]} day_active={_state[1]} ending={_state[2]}")
        if in_level and not is_day_active(game_version):
            _clear_part_anim_mailbox(ctx)
        if ending and not ctx.finished_game:
            await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            ctx.finished_game = True
        handlers = list(always_handlers) if story_active and not ending else []
        if save_active and not ending:
            handlers = list(save_active_handlers) + handlers
        # In-level handlers read/write volatile level objects (pelletMgr and radar
        # via handle_parts -> despawn, squad, etc.). During an in-level cutscene
        # mIsPauseAllowed becomes FALSE and these objects are torn down/reused by
        # rendering; touching them would corrupt the GPU stream. So only run them
        # while gameplay is actually interactive.
        if in_level and is_day_active(game_version):
            handlers = list(in_level_handlers) + handlers
        # Detect Olimar's death, even during his death sequence.
        if in_level and not ending:
            handlers = [detect_olimar_death] + handlers

        # Each handler is isolated: an exception in one must not kill the whole
        # loop, which would silently stop Pikmin, location, day cycle and area
        # detection.
        for handler in handlers:
            if ctx.exit_event.is_set():
                break  # shutdown requested mid-tick
            try:
                await handler(ctx, game_version)
            except Exception:
                logger.exception(f"[Pikmin] Error in {handler.__name__} "
                                 f"- the loop continues.")
        # TODO if "DeathLink" in ctx.tags: handle that

        # Language detection: read gsys->mLanguageID every tick.
        # If the read fails, silently keep the previous value.
        lang_code = read_game_language(game_version)
        if lang_code and lang_code != ctx.detected_language:
            msg = LANG_MSG_DETECTED.get(lang_code, LANG_MSG_DETECTED["en"])
            logger.info(f"[Pikmin] {msg} : {LANG_NAMES.get(lang_code, lang_code)}")
            ctx.detected_language = lang_code


def run_client(*args) -> None:
    # args may contain the path to a .appik1 file when launched via double-click
    appik1_path = args[0] if args and isinstance(args[0], str) and args[0].endswith(".appik1") else None

    Utils.init_logging("PikminClient")

    for problem in _check_translation_tables():
        logger.warning(f"[Pikmin] Translation table: {problem}")

    parser = get_base_parser()
    parser.add_argument("appik1_file", default="", type=str, nargs="?",
                        help="Path to a .appik1 patch file")
    parsed = parser.parse_args()

    # Resolve patch path from args or CLI argument
    patch_path = appik1_path or parsed.appik1_file

    # Patch synchronously here, BEFORE any asyncio loop and before the GUI opens,
    # so the file picker and messagebox run on the main thread with a parent window.
    if patch_path and os.path.isfile(patch_path):
        _handle_patch(patch_path)

    async def main() -> None:
        ctx = P1Context(parsed.connect, parsed.password)
        # The connection (address given as argument / via the .appik1) is deferred
        # until Pikmin is detected in Dolphin.
        if parsed.connect:
            ctx._pending_connect = parsed.connect
        else:
            logger.info("Please connect to an Archipelago server.")

        if tracker_loaded:
            ctx.run_generator()  # prepare Universal Tracker
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()

        loop_task = asyncio.create_task(dolphin_loop(ctx), name="game loop")

        # Closing the window must ALWAYS lead to exit, even if kvui.on_stop
        # (which sets exit_event) is never called.
        exit_wait = asyncio.create_task(ctx.exit_event.wait(), name="exit wait")
        waiters = {exit_wait}
        if ctx.ui_task:
            waiters.add(ctx.ui_task)
        await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
        if not ctx.exit_event.is_set():
            logger.info("[Pikmin] UI closed without exit event — forcing client exit.")
            ctx.exit_event.set()
        exit_wait.cancel()
        # Each shutdown step is time-bounded so none can block client exit forever.
        try:
            await asyncio.wait_for(loop_task, timeout=2.0)
        except BaseException:
            loop_task.cancel()
        ctx.server_address = None
        try:
            await asyncio.wait_for(ctx.shutdown(), timeout=3.0)
        except BaseException as e:
            logger.debug(f"Shutdown incomplete: {e!r}")

    import colorama
    colorama.init()
    try:
        asyncio.run(main())
    finally:
        colorama.deinit()
        # The AP session is closed and local persistent storage is written
        # synchronously on every change. Exit immediately so interpreter
        # finalization (executor thread joins, Kivy/SDL teardown, DME threads)
        # cannot block window close.
        try:
            faulthandler.cancel_dump_traceback_later()
        except Exception:
            pass
        logging.shutdown()
        os._exit(0)


def _ask_target_version() -> Optional[bytes]:
    """Show a two-button window asking which Pikmin version to patch.

    Returns the chosen Game ID, or None if the user closes the window.
    Called from the main thread, before the GUI starts.
    """
    from .P1Rom import PAL_GAME_ID, NTSC_GAME_ID

    try:
        import tkinter as tk
    except Exception as e:
        logger.warning(f"[Pikmin] tkinter unavailable ({e}) — defaulting to PAL.")
        return PAL_GAME_ID

    choice: dict[str, bytes] = {}

    root = tk.Tk()
    root.title("Pikmin — Archipelago")
    root.resizable(False, False)

    tk.Label(
        root,
        text="Which version of Pikmin do you want to patch?",
        padx=24, pady=16,
    ).pack()

    row = tk.Frame(root)
    row.pack(padx=24, pady=(0, 20))

    def pick(game_id: bytes) -> None:
        choice["v"] = game_id
        root.destroy()

    tk.Button(row, text="PAL (Europe)", width=18,
              command=lambda: pick(PAL_GAME_ID)).pack(side="left", padx=6)
    tk.Button(row, text="NTSC-U (USA)", width=18,
              command=lambda: pick(NTSC_GAME_ID)).pack(side="left", padx=6)

    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.update_idletasks()
    # center the window
    w, h = root.winfo_width(), root.winfo_height()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"+{x}+{y}")
    root.attributes("-topmost", True)
    root.mainloop()

    return choice.get("v")


def _handle_patch(appik1_path: str) -> None:
    """Patch a copy of the user's Pikmin 1 PAL ISO when a .appik1 file is opened.

    The ISO path comes from the AP settings (`pikmin_options.iso_file`). If it is
    missing from host.yaml or invalid, AP opens a native file picker itself and
    saves the choice to host.yaml.
    Called synchronously from the main thread, before the GUI.
    """
    from .P1Rom import verify_iso, patch_iso, InvalidISOError, expected_iso_help, make_disc_title
    from . import get_base_rom_path
    from settings import get_settings
    import shutil

    from .P1Rom import NTSC_GAME_ID, VERSION_LABELS

    target = _ask_target_version()
    if target is None:
        logger.info("[Pikmin] Patch cancelled by the user.")
        return
    logger.info(f"[Pikmin] Selected version: {VERSION_LABELS.get(target, target)}")

    setting_name = "iso_file_ntsc" if target == NTSC_GAME_ID else "iso_file"

    try:
        iso_path = get_base_rom_path(target)
    except Exception as e:
        # The user cancelled the picker, or the chosen file is invalid.
        msg = (
            f"No valid Pikmin 1 {VERSION_LABELS.get(target, '')} ISO was provided.\n\n"
            f"Details: {e}\n\n"
            "You can also set the path manually in host.yaml:\n"
            "  pikmin_options:\n"
            f"    {setting_name}: C:/path/to/Pikmin1.iso"
        )
        logger.error(f"[Pikmin] {msg}")
        Utils.messagebox("Cannot Patch Pikmin 1", msg, error=True)
        return

    if not iso_path or not os.path.isfile(iso_path):
        msg = (
            "No valid Pikmin 1 ISO found.\n\n"
            "Set the ISO path in host.yaml:\n"
            "  pikmin_options:\n"
            f"    {setting_name}: C:/path/to/Pikmin1.iso"
            + expected_iso_help()
        )
        logger.error(f"[Pikmin] {msg}")
        Utils.messagebox("Cannot Patch Pikmin 1", msg, error=True)
        return

    # Persist the chosen path in host.yaml (useful on first launch, right after
    # it was picked via the file picker).
    try:
        get_settings().save()
    except Exception as e:
        logger.debug(f"[Pikmin] Could not persist host.yaml: {e}")

    # Build output path: same folder as the .appik1, same name as ISO
    patch_dir = os.path.dirname(os.path.abspath(appik1_path))
    patch_basename = os.path.splitext(os.path.basename(appik1_path))[0]
    iso_ext = os.path.splitext(iso_path)[1]
    output_iso = os.path.join(patch_dir, patch_basename + iso_ext)

    # Copy the clean ISO to the output path
    try:
        shutil.copy2(iso_path, output_iso)
        logger.info(f"[Pikmin] Copied clean ISO to: {output_iso}")
    except Exception as e:
        Utils.messagebox("Cannot Patch Pikmin 1", f"Could not copy ISO:\n{e}", error=True)
        return

    # Read seed + options from .appik1
    seed = ""
    suffix = ""
    slot_name = ""
    disable_trip = True
    skip_part_collect = True
    skip_ship_upgrade = True
    try:
        import zipfile, json
        with zipfile.ZipFile(appik1_path, "r") as zf:
            with zf.open("patch.appik1") as f:
                data = json.load(f)
                seed = str(data.get("Seed", ""))
                suffix = str(data.get("GameIdSuffix", ""))  # empty = old .appik1
                slot_name = str(data.get("Name", ""))
                opts = data.get("Options", {})
                # Disable Pikmin Trip : 0=off, 1=patch (DOL), 2=item (runtime).
                # Only apply the DOL patch for "patch" mode.
                trip_mode = int(opts.get("disable_pikmin_trip", 1))
                disable_trip = (trip_mode == 1)
                # Skips are merged into the skip_events OptionSet (JSON list).
                skips = set(opts.get("skip_events", []))
                skip_part_collect = "Part Collection" in skips
                skip_ship_upgrade = "Ship Upgrade" in skips
    except Exception as e:
        logger.warning(f"[Pikmin] Could not read seed/options from .appik1: {e}")

    # Verify and patch the copy
    try:
        verify_iso(output_iso)
        status = patch_iso(output_iso, seed=seed, disable_trip=disable_trip,
                           skip_part_collect=skip_part_collect,
                           skip_ship_upgrade=skip_ship_upgrade,
                           suffix=suffix,
                           title=make_disc_title(seed, slot_name) if seed else "",
                           slot_name=slot_name) or {}
        logger.info(f"[Pikmin] ISO patched successfully: {output_iso}")
        trip_line = ""
        if disable_trip:
            trip_line = ("\n\nDisable Pikmin Trip: applied."
                         if status.get("trip_patched")
                         else "\n\nDisable Pikmin Trip: could NOT be applied "
                              "(trip code not located in this ISO revision).")
        pc_line = ""
        if skip_part_collect:
            # Success is not shown; only failure is reported.
            if not status.get("part_collect_patched"):
                pc_line = ("\n\nSkip Part Collection Cutscene: could NOT be applied "
                           "(code not located in this ISO revision).")
        su_line = ""
        if skip_ship_upgrade:
            if not status.get("ship_upgrade_patched"):
                su_line = ("\n\nSkip Ship Upgrade Cutscene: could NOT be applied "
                           "(code not located in this ISO revision).")
        sn_line = ""
        if slot_name and not status.get("slot_name_written"):
            sn_line = ("\n\nSlot name could NOT be stored in the ISO "
                       "(the client will ask for it when connecting).")
        # Animation of parts validated by the server.
        if status.get("part_anim_patched") is False:
            sn_line += ("\n\nShip part animation hook could NOT be applied: parts collected "
                        "by the server will appear on the ship the next day.")
        if status.get("death_cause_patched") is False:
            sn_line += ("\n\nDeath cause hook could NOT be applied: DeathLink messages "
                        "will not name the cause of death.")
        # NTSC only (key absent on PAL).
        if status.get("card_filename_patched") is False:
            sn_line += ("\n\nSave file name could NOT be patched: saving may not work "
                        "on this NTSC ISO.")
        Utils.messagebox(
            "Pikmin 1 Patched",
            f"Patched ISO created successfully!\n{output_iso}{trip_line}{pc_line}{su_line}{sn_line}"
        )
    except InvalidISOError as e:
        logger.error(f"[Pikmin] ISO verification failed: {e}")
        try:
            os.remove(output_iso)
        except Exception:
            pass
        # Show expected ISOs + SHA-1 of the provided file to help the player.
        Utils.messagebox("Cannot Patch Pikmin 1", str(e) + "\n" + expected_iso_help(iso_path), error=True)
    except Exception as e:
        logger.error(f"[Pikmin] Unexpected error during patching: {e}")
        try:
            os.remove(output_iso)
        except Exception:
            pass
        Utils.messagebox("Cannot Patch Pikmin 1", f"Unexpected error:\n{e}", error=True)


if __name__ == "__main__":
    run_client()
