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

import dolphin_memory_engine as dme

import Utils
from Utils import async_start
from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus

# #37 : Universal Tracker integre au client (onglet "Tracker") s'il est installe.
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
    """Adresse d'un champ de `gameflow`, par version (source: decomp)."""
    return {g: t[field] for g, t in SYM_GAMEFLOW.items()}


# Derive de la decomp -- gameflow+0x1CB / +0x2F8 / +0x2FF.
UNLOCKED_AREAS: MemoryAddress = _gf("UNLOCKED_AREAS")
# FIX NTSC: ces deux adresses utilisaient par erreur la valeur PAL en NTSC.
TIME_HOURS: MemoryAddress = _gf("TIME_HOURS")   # int, 7=matin, >=19=fin de journee
DAY_NUMBER: MemoryAddress = _gf("DAY_NUMBER")   # byte, jour courant
# Heap (alloue dynamiquement): aucun symbole statique, valeurs trouvees a la main.
COUNT_TOTAL_PARTS: MemoryAddress = mem(0x812427FF, 0x81249DE7)  # byte
COUNT_REQUIRED_PARTS: MemoryAddress = mem(0x81242803, 0x81249DEB)  # byte

# Ship part hint text address (PAL) — universal for all parts
# Ancienne adresse PAL codee en dur. Plus utilisee pour lire/ecrire : l'adresse
# est desormais resolue via resolve_ship_part_text_addr(). Conservee uniquement
# comme valeur de reference dans /debugtext.
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

# Synchronisation AP active (une partie vient d'etre chargee), par langue du jeu.
# Options actives annoncees a la connexion, par langue du jeu.
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

# #38 : connexion differee jusqu'a la detection du jeu.
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

# Synchronisation AP en pause (retour a un menu), par langue du jeu.
SYNC_PAUSED_MSG = {
    "en": "Returned to menu — AP sync paused.",
    "fr": "Retour au menu — synchronisation AP en pause.",
    "de": "Zurück zum Menü — AP-Synchronisierung pausiert.",
    "it": "Ritorno al menu — sincronizzazione AP in pausa.",
    "es": "Vuelta al menú — sincronización AP en pausa.",
}

# DeathLink recu : Olimar est tue, par langue du jeu.
DEATHLINK_RECEIVED_MSG = {
    "en": "DeathLink received — Olimar has been eliminated.",
    "fr": "DeathLink reçu — Olimar est éliminé.",
    "de": "DeathLink erhalten — Olimar wurde ausgeschaltet.",
    "it": "DeathLink ricevuto — Olimar è stato eliminato.",
    "es": "DeathLink recibido — Olimar ha sido eliminado.",
}

def _read_apworld_version() -> str:
    """Version de l'apworld, lue depuis archipelago.json (manifeste).

    Fonctionne en source (dossier) comme en .apworld (zip) : on essaie d'abord
    importlib.resources (gere le zip), puis un simple acces fichier en repli.
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

# id d'objet -> nom lisible (bonus Pikmin), pour les logs de debug.
ITEM_ID_TO_NAME: dict[int, str] = {ap_id: name for name, ap_id in FILLER_ITEMS.items()}


def _named_counts(applied: dict) -> dict:
    """Remplace les id d'objets par leur nom lisible dans un dict {id: n}.

    Trie par nom d'objet pour une lecture stable, et garde l'id brut en repli si
    un id est inconnu.
    """
    out = {}
    for item_id, n in applied.items():
        name = ITEM_ID_TO_NAME.get(item_id, f"#{item_id}")
        out[name] = n
    return dict(sorted(out.items()))

# Detection de langue.
#
# Ancienne methode : comparer des chaines d'interface ("PRESS START", ...) a des
# adresses codees en dur. Fragile (adresses non issues de la decomp, PAL
# uniquement, valable seulement a l'ecran titre).
#
# Nouvelle methode : lire `gsys->mLanguageID` (StdSystem, include/system.h de la
# decomp projectPiki/pikmin). `gsys` est un pointeur global, mLanguageID est a
# l'offset 0x1A0. Valable a tout moment de la partie.
#
# NTSC-U : le champ n'existe pas (le jeu est anglais uniquement) et 0x1A0 y
# porte le pointeur de vtable -> on ne lit jamais, on renvoie "en".

# Bornes plausibles pour un pointeur en MEM1/MEM2 (validation anti-lecture sauvage).
_RAM_MIN = 0x80000000
_RAM_MAX = 0x81800000


def resolve_ship_part_text_addr(game: Game) -> Optional[int]:
    """Adresse du buffer de texte actuellement affiche, ou None.

    Suit la chaine de pointeurs issue de la decomp :
        tutorialWindow (statique) -> ogScrTutorialMgr
          +0x00  mMessageMgr      -> ogScrMessageMgr
          +0x4F2 mFormattedDisplayStrings[0]

    Remplace l'ancienne adresse de tas codee en dur (0x807B100A), qui n'etait
    valable qu'en PAL. La chaine ne depend que de symboles statiques et
    d'offsets de structures, donc elle fonctionne aussi en NTSC-U.
    Verifie en jeu : la chaine retombe exactement sur l'ancienne adresse PAL.
    """
    mgr = resolve_message_mgr(game)
    if mgr is None:
        return None
    return mgr + TUTORIAL_TEXT_CHAIN["MSGMGR_FORMATTED"]


def resolve_message_mgr(game: Game) -> Optional[int]:
    """Adresse du ogScrMessageMgr courant, ou None si aucune fenetre de texte."""
    tw_addr = SYM_TUTORIAL_WINDOW_PTR.get(game)
    if tw_addr is None:
        return None
    try:
        tut = struct.unpack(">I", dme.read_bytes(tw_addr, 4))[0]
        if not (_RAM_MIN <= tut < _RAM_MAX):
            return None  # aucune fenetre de texte active
        mgr = struct.unpack(
            ">I", dme.read_bytes(tut + TUTORIAL_TEXT_CHAIN["TUTORIALMGR_MESSAGEMGR"], 4)
        )[0]
        if not (_RAM_MIN <= mgr < _RAM_MAX):
            return None
    except Exception:
        return None
    return mgr


# Plages d'EnumTutorial que l'on accepte de remplacer par un hint.
# On affiche le hint uniquement AVANT la collecte :
#   - "discovery" : on s'approche d'une piece pour la premiere fois
#   - "info"      : on interagit avec une piece pas encore collectee
# On exclut :
#   - "collect" : texte de RECUPERATION de la piece. Y ecrire un hint sur
#     l'emplacement de la piece n'a plus de sens (on vient de l'obtenir) et
#     ecrasait le texte de recuperation.
#   - "power"   : texte d'amelioration du vaisseau, sans rapport avec un emplacement.
HINTABLE_TEXT_KINDS = ("discovery", "info")


def read_displayed_message_id(msgmgr: int) -> Optional[int]:
    """Identifiant EnumTutorial du texte actuellement affiche, ou None."""
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
    """Nom de la piece correspondant a un ID de texte, ou None si ce n'en est pas un.

    Les textes de pieces occupent des plages precises d'EnumTutorial, chacune
    couvrant les 30 pieces dans l'ordre de UfoPartIndex. Tout autre ID est un
    texte de tutoriel ou de scenario, qu'il ne faut pas toucher.
    """
    for kind in HINTABLE_TEXT_KINDS:
        base = TUT_PART_TEXT_RANGES[kind]
        if base <= msg_id < base + len(UFO_PART_ORDER):
            return UFO_PART_ORDER[msg_id - base]
    return None


def read_displayed_part(game: Game) -> Optional[str]:
    """Nom de la piece dont le texte est affiche, ou None si ce n'est pas un texte de piece.

    On identifie le texte par son ID de message (TextInfoType.mMsgUniqueId), et
    non par `gameflow.mShipTextPartID` : ce dernier est REMANENT, il conserve la
    derniere piece concernee meme pendant un texte sans rapport. C'est ce qui
    faisait ecraser les textes du tutoriel par un hint.
    """
    msgmgr = resolve_message_mgr(game)
    if msgmgr is None:
        return None
    msg_id = read_displayed_message_id(msgmgr)
    if msg_id is None:
        return None
    return part_from_message_id(msg_id)


def _oneplayer_subsection(game: Game) -> Optional[int]:
    """Sous-section OnePlayer courante (enum OnePlayerSectionID), ou None.

    Lit `gameflow.mNextOnePlayerSectionID`. Vaut :
      - ONEPLAYER_NewPikiGame (7) : Olimar dans un niveau, journee jouee ;
      - ONEPLAYER_MapSelect (6)   : carte du monde / choix de niveau ;
      - ONEPLAYER_CardSelect (1)  : menu de selection de sauvegarde.
    Renvoie None hors mode histoire (ecran titre, boot).

    `mCurrGameSectionID` (section externe) ne suffit pas : tous ces menus sont
    des sous-sections de SECTION_OnePlayer. `DAY_NUMBER` non plus : il garde une
    valeur residuelle non nulle sur ces menus.
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
    """Vrai si la journee a reellement commence (gameplay interactif).

    Lit `gameflow.mIsPauseAllowed` : TRUE seulement quand le joueur controle
    Olimar, FALSE pendant le chargement, la cinematique d'intro de journee et la
    fin de journee. Sert a mettre les traps en attente tant que la journee n'a
    pas vraiment demarre.
    """
    gf = SYM_GAMEFLOW.get(game)
    if not gf:
        return False
    try:
        return struct.unpack(">i", dme.read_bytes(gf["PAUSE_ALLOWED"], 4))[0] != 0
    except Exception:
        return False


def is_overlay_active(game: Game) -> bool:
    """#5 : vrai si un ecran couvre le gameplay (traps a suspendre).

    D'apres la decomp (newPikiGame.cpp, GameFlow) :
      - mIsUIOverlayActive (_338) : menu Pause (Start), carte/commandes (Y),
        texte de piece de vaisseau, autres fenetres par-dessus le jeu ;
      - mPauseAll (_33C) : gameplay gele (menu d'oignon, cinematique) ;
      - mIsTutorialTextActive (_340) : fenetre de texte ouverte.
    En cas d'echec de lecture on considere l'overlay actif (prudence : mieux
    vaut retarder un trap que l'appliquer menu ouvert).
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
    """Vrai si le joueur controle Olimar dans un niveau (journee en cours).

    Verrou des handlers qui LISENT de la memoire propre au niveau : collecte des
    pieces (objets sur le tas) et compteurs de Pikmin de l'escouade. Hors niveau,
    ces adresses ne sont pas pertinentes et pourraient envoyer de faux checks.
    """
    return _oneplayer_subsection(game) == ONEPLAYER_NEW_PIKI_GAME


def is_save_active(game: Game) -> bool:
    """Vrai si une partie est en cours : dans un niveau OU sur la carte du monde.

    Verrou plus large que is_in_level, pour la RECEPTION d'objets (les bonus
    Pikmin se persistent via STAGE et s'appliqueront au prochain niveau) et le
    deblocage des zones (qui doit etre visible sur la carte du monde). Exclut le
    menu de selection de sauvegarde (CardSelect) et l'ecran titre.

    Sert aussi de reference pour le message de synchronisation : sans ca, passer
    par la carte du monde entre deux niveaux affichait a tort "synchronisation en
    pause".
    """
    return _oneplayer_subsection(game) in (ONEPLAYER_NEW_PIKI_GAME, ONEPLAYER_MAP_SELECT)


def read_orima_dead(game: Game) -> bool:
    """Vrai si Olimar est mort (GameStat::orimaDead, mis a 1 par NaviDeadState)."""
    addr = SYM_ORIMA_DEAD.get(game)
    if addr is None:
        return False
    try:
        return dme.read_byte(addr) != 0
    except Exception:
        return False


def read_dead_pikis_total(game: Game) -> Optional[int]:
    """Total de Pikmin morts (GameStat::deadPikis, somme Blue+Red+Yellow), ou None."""
    addr = SYM_DEAD_PIKIS.get(game)
    if addr is None:
        return None
    try:
        blue, red, yellow = struct.unpack(">iii", dme.read_bytes(addr, 12))
    except Exception:
        return None
    return blue + red + yellow


def _resolve_olimar(game: Game) -> Optional[int]:
    """Adresse de l'objet Navi d'Olimar, ou None.

    naviMgr -> +MONO_OBJECTLIST (Creature**) -> [0] = Navi (Olimar en 1 joueur).
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
    """Tue Olimar a la reception d'un DeathLink.

    Ecrire mHealth = 0 ne suffit PAS : le jeu ne verifie la sante que dans les
    etats de degats, pas en continu. On force donc Olimar dans l'etat 'ecrase'
    (NaviPressedState) avec un timer deja ecoule : son exec(), appele chaque
    frame par le jeu, verifie alors mHealth <= 1 et declenche lui-meme la vraie
    transition vers NaviDeadState (avec toute la sequence : orimaDead, fin de
    journee, animation). C'est le jeu qui execute la transition, on ne fait
    qu'amorcer.

    Sequence :
      1. Resoudre Olimar (Navi).
      2. Retrouver l'instance NaviPressedState via les tables de la StateMachine.
      3. Ecrire mCurrState = NaviPressedState, mPressedTimer < 0, mHealth = 0.

    En cas d'echec d'une lecture, repli sur l'ecriture de mHealth seule.
    Renvoie True si l'amorce a abouti.
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

    try:
        # Toujours mettre la sante a 0.
        dme.write_bytes(navi + C["CREATURE_HEALTH"], struct.pack(">f", 0.0))

        sm = u32(navi + C["NAVI_STATEMACHINE"])
        if sm is None:
            return True  # sante a 0 ecrite, mais pas d'etat forcable
        state_indexes = u32(sm + C["SM_STATEINDEXES"])
        states = u32(sm + C["SM_STATES"])
        if state_indexes is None or states is None:
            return True
        # mStateIndexes[NAVISTATE_Pressed] -> index dans mStates
        idx = struct.unpack(">i", dme.read_bytes(state_indexes + NAVISTATE_PRESSED * 4, 4))[0]
        if idx < 0 or idx > 64:
            return True
        pressed_state = u32(states + idx * 4)
        if pressed_state is None:
            return True

        # Amorcer : timer ecoule + etat Pressed. Le exec() du jeu fera la mort.
        dme.write_bytes(navi + C["NAVI_PRESSED_TIMER"], struct.pack(">f", -1.0))
        dme.write_bytes(navi + C["NAVI_CURRSTATE"], struct.pack(">I", pressed_state))
        return True
    except Exception:
        return False


# --- Traps ---------------------------------------------------------------

# Reglages des effets de trap.
TIME_TRAP_HOURS = 2      # heures de jeu ajoutees a l'horloge
DAMAGE_TRAP_LOSS = 20.0  # % de sante retire par defaut (#43 : option damage_trap_amount)
DAMAGE_TRAP_FLOOR = 2.0  # plancher pour ne pas tuer Olimar (mort a <= 1.0)
TELEPORT_TRAP_LIFT = 60.0    # hauteur ajoutee pour retomber sur le terrain


def apply_time_trap(game: Game) -> bool:
    """Avance l'horloge : reduit le temps restant dans la journee.

    On ecrit mCurrentGameHour (l'entier de l'heure, TIME_HOURS), PAS mTimeOfDay :
    WorldClock::update recalcule mTimeOfDay chaque frame depuis mCurrentGameHour,
    donc ecrire mTimeOfDay etait immediatement ecrase (Time Trap sans effet).
    """
    gf = SYM_GAMEFLOW.get(game)
    if not gf:
        return False
    addr = gf["TIME_HOURS"]
    try:
        h = struct.unpack(">i", dme.read_bytes(addr, 4))[0]
        # #42 : plafond a l'heure de fin de journee (19h). Au-dela, le jeu
        # enregistrerait le point du graphique hors de son tableau
        # (TimeGraph::set sans verification -> ecriture memoire hors limites).
        graph = _read_population_graph(game)
        end = graph[2] if graph else 19
        new = min(h + TIME_TRAP_HOURS, end)
        if new > h:
            dme.write_bytes(addr, struct.pack(">i", new))
        _fill_population_graph_gaps(game)
        return True
    except Exception:
        return False


# --- #42 : graphique de population et Time Trap --------------------------------
# PlayerState::mPerHourGraph (TimeGraph @ PlayerState+0x18C) : u16 mStartTime,
# u16 mEndTime, PikiNum* mEntries (int[3] Blue/Red/Yellow par heure, -1 = vide).
# Le jeu n'enregistre un point qu'au CHANGEMENT d'heure ; un Time Trap saute
# des heures, qui restent a -1, et le dessin s'arrete au premier -1 (ogGraph) :
# plusieurs traps tot dans la journee = graphique vide. On comble les heures
# sautees avec la valeur de l'heure precedente (courbe plate).

def _read_population_graph(game: Game) -> Optional[tuple]:
    """(adresse des entrees, heure de debut, heure de fin) ou None."""
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
    """Remplit les heures sautees (-1) jusqu'a l'heure courante."""
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
    """#42 : comble les trous du graphique (Time Trap, TrapLink...) a chaque tick."""
    _fill_population_graph_gaps(game)


def apply_end_day_trap(game: Game) -> bool:
    """Force la fin de la journee : ecrit gameflow.mIsDayEndTriggered.

    La sequence de fin de journee (OnePlayerSection) consomme ce flag "hors menu"
    et demarre la cinematique de fin de journee via gameflow.mGameInterface. Si on
    arme le flag a un mauvais moment, le consommateur deref un pointeur nul et lit
    a l'offset +0xEC (crash "Invalid read from 0x000000ec", menu de fin de journee
    qui ne s'affiche plus). Deux cas dangereux :
      - la fin de journee est deja active ou en attente (coucher de soleil, mort
        d'Olimar, ou un End Day Trap precedent pas encore consomme) ;
      - mGameInterface est nul (transition de section en cours).
    On n'arme donc le flag que dans un etat stable ; sinon on renvoie False et le
    trap reste en attente pour se rejouer a la prochaine journee propre.

    Offsets deduits de include/gameflow.h autour de mCurrGameSectionID (_1EC) :
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
        # Fin de journee deja active ou deja armee : ne pas re-declencher.
        if struct.unpack(">h", dme.read_bytes(day_end_active, 2))[0] != 0:
            return False
        if struct.unpack(">h", dme.read_bytes(gf["DAY_END_TRIGGERED"], 2))[0] != 0:
            return False
        # mGameInterface doit pointer sur un objet valide : c'est lui que la
        # cinematique de fin de journee deref (source directe du crash +0xEC).
        gi = struct.unpack(">I", dme.read_bytes(game_interface_ptr, 4))[0]
        if not (_RAM_MIN <= gi < _RAM_MAX):
            return False
        dme.write_bytes(gf["DAY_END_TRIGGERED"], struct.pack(">h", 1))
        return True
    except Exception:
        return False


DAMAGE_TRAP_MAX_HEALTH = 100.0  # sante max d'Olimar


def apply_damage_trap(game: Game, ctx=None) -> bool:
    """Blesse Olimar de `damage_trap_amount` % de sa sante max (#43).

    Option `damage_trap_can_kill` : si la sante tombe au seuil de mort du jeu
    (<= 1.0), Olimar meurt (vraie sequence de mort via kill_olimar, qui declenche
    aussi le DeathLink classic) ; sinon on laisse DAMAGE_TRAP_FLOOR PV.
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
                if kill_olimar(game) and ctx is not None:
                    ctx._client_kill_reason = "Damage Trap"
                return True
            new = DAMAGE_TRAP_FLOOR
        # Ne jamais soigner : si Olimar est deja plus bas, on laisse tel quel.
        if new < h:
            dme.write_bytes(addr, struct.pack(">f", new))
        return True
    except Exception:
        return False


WP_FLAG_PEBBLE = 0x02         # WayPointFlags::Pebble (obstacle)
WP_LINKS_OFF = 0x14           # int mLinkIndices[8]
WP_LINKCOUNT_OFF = 0x34       # int mLinkCount


def _read_waypoint_graph(game: Game) -> Optional[list]:
    """#48 : lit tout le reseau de waypoints (groupe 0) en une lecture.

    Renvoie une liste de dicts {pos, open, flags, links} ou None.
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
    """#48 : Teleport Trap intelligent.

    Part du waypoint ouvert le plus proche d'Olimar et ne garde que les waypoints
    atteignables A PIED dans les deux sens (aller ET retour) en ne traversant que
    des waypoints ouverts : portes fermees, ponts non construits et obstacles
    (waypoints fermes par le jeu) coupent le chemin. Exclut l'eau et les
    waypoints marques "Pebble". Aucun soft lock : Olimar peut toujours revenir.
    """
    graph = _read_waypoint_graph(game)
    if not graph:
        return None
    ox, oy, oz = origin

    def usable(i: int) -> bool:
        return graph[i]["open"] and not (graph[i]["flags"] & WP_FLAG_INWATER)

    # Point de depart : waypoint utilisable le plus proche (hauteur penalisee
    # pour ne pas choisir un point au-dessus/en dessous d'une falaise).
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
    """#48 : teleporte Olimar sur un waypoint sur (aller-retour a pied possible).

    Si aucun point sur n'est trouve, renvoie False : le trap reste en attente et
    sera retente au tick suivant (plus de decalage aleatoire, source de soft lock).
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
    """Pointeur de l'instance d'etat `state_id` via les tables de la StateMachine."""
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
    """Disperse l'escouade de facon deterministe.

    L'injection de la touche de disband etait trop dependante du timing des
    frames. A la place on exploite le meme mecanisme que le jeu :
      - NaviWalkState::exec transite vers NAVISTATE_Stuck des que
        Creature.mStickListHead est non-nul ;
      - NaviStuckState::init appelle releasePikis() -> la dispersion.
    On force donc l'etat Walk et on met mStickListHead non-nul : le jeu execute
    lui-meme la vraie transition et le disband. On remet ensuite mStickListHead a
    zero pour que Stuck::exec ramene Olimar en Walk.
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
        # Forcer l'etat Walk (pour que son exec tourne) + amorcer le "stuck".
        # mStickListHead = navi : pointeur non-nul et valide (evite tout deref
        # sauvage si quelque chose le lit avant qu'on le remette a zero).
        dme.write_bytes(curr_addr, struct.pack(">I", walk_state))
        dme.write_bytes(stick_addr, struct.pack(">I", navi))
    except Exception:
        return False
    # Laisser quelques frames au jeu pour transiter vers Stuck et disperser.
    await asyncio.sleep(0.1)
    try:
        # Vider la liste : Stuck::exec ramene alors Olimar en Walk.
        dme.write_bytes(stick_addr, struct.pack(">I", 0))
    except Exception:
        pass
    return True


# Appliers synchrones (une ecriture). Le disband est asynchrone (rafale) et
# traite a part dans apply_trap.
TRAP_APPLIERS = {
    "time":     apply_time_trap,
    "end_day":  apply_end_day_trap,
    "damage":   apply_damage_trap,
    "teleport": apply_teleport_trap,
}


# --- #7 Trip Trap ----------------------------------------------------------
#
# Test de trebuchement (ActCrowd::exec, aiCrowd.cpp) :
#     if (getRand(1.0f) >= 0.9999f && getRand(1.0f) > 0.7f) -> trebuche
# Il est evalue pour chaque Pikmin qui suit Olimar en courant (> 110 u/s) tous
# les 100 unites parcourues. Le Trip Trap remplace la constante 0.9999 (copie
# propre a ce test en .sdata2, SYM_TRIP_RAND_CONST) par 0.0 pendant
# TRIP_TRAP_SECONDS : le 1er test est toujours vrai -> ~30 % de chance a chaque
# test, donc quasiment toute l'escouade en mouvement trebuche (animation normale
# du jeu, PIKIANIM_Korobu). Ensuite on remet la valeur normale (0.9999, ou 2.0
# si Trip Immunity est actif). C'est une DONNEE : le JIT de Dolphin la relit.
# Le temps ne s'ecoule que pendant le gameplay interactif (pas en pause/menu).

TRIP_TRAP_SECONDS = 10.0


def _trip_mode(ctx) -> int:
    """Option Disable Pikmin Trip : 0 off, 1 always (ISO patchee), 2 item."""
    slot_data = getattr(ctx, "slot_data", None) or {}
    return int(slot_data.get("disable_pikmin_trip", 1))


def _trip_immune(ctx) -> bool:
    """Vrai si les Pikmin ne peuvent plus trebucher (always, ou item recu)."""
    mode = _trip_mode(ctx)
    if mode == 1:
        return True
    if mode == 2:
        return any(it.item == TRIP_IMMUNITY_ITEM_ID for it in ctx.items_received)
    return False


def _trip_normal_value(ctx) -> float:
    return TRIP_DISABLED_FLOAT if _trip_immune(ctx) else TRIP_NORMAL_FLOAT


def apply_trip_trap(ctx, game: Game) -> bool:
    """Demarre (ou relance) le Trip Trap. Toujours True : consomme le trap."""
    if ctx is None:
        return False
    if _trip_immune(ctx):
        # Choix de design : immunite (item Trip Immunity / option always) ->
        # trap consomme sans effet.
        if ctx.debug_trap:
            logger.info("[DEBUG TRAP] Trip Trap sans effet : Pikmin immunises.")
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
    """Remet la constante de trip a sa valeur normale (fin de trap / fermeture)."""
    addr = SYM_TRIP_RAND_CONST.get(game)
    if addr is None:
        return
    try:
        dme.write_bytes(addr, struct.pack(">f", _trip_normal_value(ctx)))
    except Exception:
        pass


async def handle_trip_trap_timer(ctx, game: Game) -> None:
    """Decompte du Trip Trap et restauration de la constante."""
    addr = SYM_TRIP_RAND_CONST.get(game)
    if addr is None:
        return
    if ctx._trip_trap_remaining <= 0:
        # Securite : constante restee forcee (client ferme pendant un trap,
        # reconnexion...) -> on la remet d'aplomb.
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
            logger.info("[DEBUG TRAP] Trip Trap termine.")
    else:
        try:
            dme.write_bytes(addr, struct.pack(">f", TRIP_FORCED_FLOAT))
        except Exception:
            pass


async def report_client_kill(ctx) -> None:
    """#43 : envoie le DeathLink d'une mort d'Olimar provoquee par le client
    (Damage Trap, lien Olimar/Pikmin).

    La detection "classic" (front montant de orimaDead dans handle_death_link)
    ne tourne que pendant le gameplay interactif ; or la mort coupe aussitot
    le gameplay (debut de la sequence de fin de journee) : le front n'etait
    jamais vu et aucun DeathLink ne partait. On l'envoie donc directement, et
    on neutralise la detection pour ne pas l'envoyer une 2e fois.
    """
    reason = getattr(ctx, "_client_kill_reason", None) or "the client"
    ctx._client_kill_reason = None
    # Joueur a l'origine (Damage Trap : slot qui a envoye le trap / source TrapLink).
    source = getattr(ctx, "_trap_source", None) if reason == "Damage Trap" else None
    ctx._suppress_orima_send = True
    if getattr(ctx, "death_link_mode", 0) not in (1, 3):  # classic / both
        return
    if getattr(ctx, "_deathlink_locked_this_day", False):
        return
    name = ctx.player_names.get(ctx.slot, "Olimar")
    if source:
        await ctx.send_death(f"{name} was taken down by a {reason} from {source}.")
    else:
        await ctx.send_death(f"{name} was taken down by the {reason}.")
    ctx._deathlink_locked_this_day = True


async def apply_trap(game: Game, kind: str, ctx=None) -> bool:
    """Applique un trap par type interne. Renvoie True si applique."""
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
    """Renvoie le code langue courant, ou None si illisible.

    Toute valeur inattendue (pointeur nul, hors RAM, ID hors enum) renvoie None
    plutot qu'une langue fausse : l'appelant conserve alors la valeur precedente.
    """
    if game != b"GPIP01":
        # NTSC-U (et tout le reste) : anglais uniquement.
        return "en"

    gsys_ptr_addr = SYM_GSYS_PTR.get(game)
    if gsys_ptr_addr is None:
        return None

    try:
        gsys = struct.unpack(">I", dme.read_bytes(gsys_ptr_addr, 4))[0]
        if not (_RAM_MIN <= gsys < _RAM_MAX):
            return None  # pas encore initialise au tout debut du boot
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
    # Attention a la casse : la cle doit correspondre EXACTEMENT a ALL_PARTS
    # (P1Data.py). C'etait "Repair-Type Bolt" ici contre "Repair-type Bolt" dans
    # ALL_PARTS, donc cette piece n'etait traduite dans aucune langue.
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

# Langues traduites (l'anglais utilise directement les cles de ALL_PARTS).
TRANSLATED_LANGS = ("fr", "de", "it", "es")


def _check_translation_tables() -> list[str]:
    """Verifie que chaque piece de ALL_PARTS a bien une traduction par langue.

    Une simple faute de casse dans une cle desactivait silencieusement la
    traduction d'une piece pour le hint mode. On journalise desormais l'ecart
    au demarrage au lieu de le laisser passer inapercu.
    """
    problems: list[str] = []
    for part_name in ALL_PARTS:
        entry = SHIP_PART_TRANSLATIONS.get(part_name)
        if entry is None:
            problems.append(f"aucune traduction pour la piece {part_name!r}")
            continue
        for lang in TRANSLATED_LANGS:
            if not entry.get(lang):
                problems.append(f"{part_name!r} : traduction {lang} manquante")
    for key in SHIP_PART_TRANSLATIONS:
        if key not in ALL_PARTS:
            problems.append(f"cle de traduction {key!r} inconnue de ALL_PARTS")
    return problems


# Libelles du hint, par langue. Le texte etait auparavant toujours en anglais,
# meme quand le jeu tournait dans une autre langue.
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
    """Nom de la piece dans la langue detectee, avec repli sur l'anglais."""
    if lang == "en":
        return part_name
    translated = SHIP_PART_TRANSLATIONS.get(part_name, {}).get(lang)
    if translated:
        return translated.decode("latin-1")
    return part_name


def _encode_hint(text: str) -> bytes:
    """Encode le texte du hint pour le moteur de texte du jeu.

    Le jeu utilise un jeu de caracteres latin-1 : encoder en ASCII transformait
    tous les accents en '?' (noms de joueurs, d'objets et libelles traduits).
    """
    result = text.encode("latin-1", errors="replace")
    if len(result) > SHIP_PART_TEXT_LENGTH:
        result = result[:SHIP_PART_TEXT_LENGTH]
    if len(result) < SHIP_PART_TEXT_LENGTH:
        result += b"\x00" * (SHIP_PART_TEXT_LENGTH - len(result))
    return result


# ---------------------------------------------------------------------------
# Adresses derivees de la decompilation (projectPiki/pikmin) via P1Symbols.py.
# PAL et NTSC-U sont desormais fournis pour TOUTES les tables ci-dessous ;
# auparavant seul le PAL existait, ce qui desactivait silencieusement les
# items Pikmin en NTSC.
# ---------------------------------------------------------------------------

# formationPikis__8GameStat -- octet de poids faible du u32 (big-endian).
# Sert au check de locations.
PIKMIN_ADDRESSES = SYM_PIKMIN_ADDRESSES

# GameStat::containerPikis__8GameStat -- total live par couleur (Pikmin
# actuellement "dans un oignon"), incremente par le jeu en temps reel des
# qu'un Piki entre/sort d'un oignon (goalItem.cpp, itemAI.cpp).
ONION_DYN_ADDRS = SYM_ONION_DYN_ADDRS

# GameStat::allPikis__8GameStat -- LE total reellement affiche au HUD
# (bas-droite, "compteur total tout confondu") et sur l'ecran de resultats,
# via zen::pGameInfo->mTotalPikiNum = GameStat::allPikis (gameCoreSection.cpp).
# Recalcule uniquement quand GameStat::update() tourne (evenements de jeu
# reels : Piki qui entre/sort d'un oignon, formation, etc., ou une fois par
# jour au chargement du niveau) -- jamais a partir de pikiInfMgr.mPikiCounts
# en continu. C'est pour ca qu'ecrire seulement STAGE ne change rien tant
# que le jeu ne refait pas ce calcul lui-meme.
GAMESTAT_ALLPIKIS_ADDRS = SYM_ALLPIKIS_ADDRS

# Sentinelle de debut de journee: gameflow+0x2EC (0 au menu, non-nul en jeu).
ONION_DYN_SENTINEL = _gf("SENTINEL")

# pikiInfMgr.mPikiCounts[couleur][stade], u32 chacun.
# Le jeu recalcule seul le total affiche = Leaf + Bud + Flower.
ONION_STAGE_ADDRS_CLIENT = SYM_ONION_STAGE_ADDRS


class P1CommandProcessor(SuperCommandProcessor):
    def __init__(self, ctx: CommonContext):
        super().__init__(ctx)

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
            return v if 0x80000000 <= v < 0x81800000 else 0

        def obj_info(obj):
            """(objType, model_id, ap_id, name, is_alive) d'un objet, ou None."""
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

        # --- pelletMgr : TOUS les slots (meme mEntryStatus != 0), pour reperer
        #     un pellet tenu/avale par une creature.
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
                    continue  # seulement les pellets de PIECES (model connu)
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

        # --- radar : liste des icones reellement dessinees sur la carte.
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
                        # Le nœud pointe vers une CREATURE (ex. Snake/Snagret) qui
                        # CONTIENT une piece : on cherche comment elle la reference,
                        # en scannant son objet pour un fourCC de piece connu OU un
                        # pointeur vers un Pellet/PelletConfig de piece (issue #11).
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
                                if 0x80000000 <= p < 0x81800000:
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


# --- #2 : fermeture du client ------------------------------------------------

# Delai max (s) entre le clic sur la croix (ou /exit) et la fin du processus.
EXIT_WATCHDOG_SECONDS = 6
_exit_watchdog_file = None


_exit_watchdog_armed = False


def _arm_exit_watchdog() -> None:
    """#2 : garantit que le processus se termine apres une demande de fermeture.

    Symptome : clic sur la croix en pleine journee, connecte -> Kivy sort de sa
    boucle ("Leaving application in progress...") puis plus rien : la fenetre
    ne repond plus jusqu'a ce que Windows tue le processus.

    faulthandler.dump_traceback_later() arme un minuteur en C, independant du
    GIL et de la boucle asyncio : s'il n'est pas annule a temps, il ecrit la
    pile de TOUS les threads dans le log (pour savoir ou ca bloquait) puis
    termine le processus. Ca marche meme si le thread principal est coince
    dans un appel C (dolphin_memory_engine, Kivy/SDL, join de thread...).
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
        stream.write(f"\n[Pikmin] Fermeture demandee : si le client n'est pas ferme dans "
                     f"{EXIT_WATCHDOG_SECONDS}s, les piles des threads sont ecrites ci-dessous "
                     f"et le processus est termine de force.\n")
        stream.flush()
        faulthandler.dump_traceback_later(EXIT_WATCHDOG_SECONDS, exit=True, file=stream)
    except Exception as e:
        logger.debug(f"Exit watchdog not armed: {e}")


class _P1ExitEvent(asyncio.Event):
    """exit_event qui arme le chien de garde de fermeture (#2) des qu'il est
    leve : par la croix de la fenetre (kvui.on_stop), /exit, ou autre."""

    def set(self) -> None:
        if not self.is_set():
            _arm_exit_watchdog()
        super().set()


class P1Context(SuperContext):
    command_processor = P1CommandProcessor
    game: str = "Pikmin"
    items_handling: int = 0b111
    # #37 : UT ajoute le tag "Tracker" (connexion en simple tracker) ; ici on
    # joue vraiment, donc on garde les tags d'un client de jeu normal.
    tags = {"AP"}

    def __init__(self, server_address: Optional[str], password: Optional[str]) -> None:
        super().__init__(server_address, password)
        self.items_handling = 0b111  # UT le redefinit dans son __init__
        # #38 : jeu detecte dans Dolphin / connexion en attente / slot lu dans l'ISO.
        self.game_detected: bool = False
        self._pending_connect: Optional[str] = None
        self.iso_slot_name: str = ""
        self._detected_game_id: Optional[bytes] = None
        # #2 : exit_event qui arme le chien de garde de fermeture.
        self.exit_event = _P1ExitEvent()
        self.dolphin_status_text = "Disconnected"

        # Track Pikmin counts for location checking
        self.pikmin_counts = {"red": 0, "yellow": 0, "blue": 0}
        self.pikmin_location_ids = {}
        self.last_red_count = 0
        self.last_yellow_count = 0
        self.last_blue_count = 0

        # Track how many Pikmin bonus items have already been applied
        self.pikmin_items_applied: dict[int, int] = {}
        # #4 Custom Save : bonus Pikmin appliques, par sauvegarde du jeu
        # (cle = checksum du fichier, hex). Voir track_game_save().
        self.game_saves: dict[str, dict] = {}
        self._save_prev_sub: Optional[int] = None
        self._save_crc: Optional[int] = None
        self._pending_save_load: Optional[tuple] = None
        # #33 : bonus Pikmin recus hors journee, a compter comme "germes" au
        # debut de la prochaine journee (couleur -> nombre).
        self._pending_born: dict[str, int] = {"red": 0, "yellow": 0, "blue": 0}
        # #34 : oignons abandonnes / nb de corrections du cone, par journee.
        self._cone_ok: set = set()
        self._cone_tries: dict = {}
        self._cone_free_since: Optional[float] = None  # #46
        self._client_kill_reason: Optional[str] = None  # #43
        self._olimar_bond_last: Optional[int] = None     # #44 : reference bornPikis
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
        # Une partie etait-elle chargee au tick precedent ? Sert a ne journaliser
        # que les transitions (chargement / retour au titre), pas chaque tick.
        self._save_was_loaded: bool = False

        # QOL Disable Pikmin Trip mode 'item' : le patch RAM du trebuchement
        # n'est applique qu'une fois, une fois l'item 'Trip Immunity' recu.
        self._trip_ram_patched: bool = False
        # #7 Trip Trap : secondes de gameplay restantes (0 = inactif).
        self._trip_trap_remaining: float = 0.0
        self._trip_trap_last: float = 0.0

        # --- DeathLink / TrapLink ---
        # Configures depuis slot_data a la connexion.
        self.death_link_mode: int = 0        # 0=off, 1=classic, 2=pikmin, 3=both
        self.pikmin_death_amount: int = 10
        self.trap_link_enabled: bool = False
        # Conversion des traps TrapLink inter-jeux inconnus : True = un trap
        # inconnu (d'un autre jeu) est converti en trap Pikmin aleatoire ; False =
        # il est ignore. `trap_link_conversion_traps` restreint le pool de traps
        # Pikmin utilisables pour la conversion (vide = tous).
        self.trap_link_conversion: bool = True
        self.trap_link_conversion_traps: list = []
        # Detection cote envoi.
        self._orima_was_dead: bool = False   # etat mort au tick precedent (front montant)
        # deadPikis est deja remis a zero par le jeu a chaque journee ; on suit
        # la valeur du tick precedent pour detecter la remise a zero (nouvelle
        # journee) et repartir le comptage des DeathLink.
        self._dead_pikis_last: Optional[int] = None
        self._dead_pikis_sent: int = 0       # nb de DeathLink deja envoyes cette journee
        # #3 Lien Olimar/Pikmin : PV perdus par Pikmin mort.
        self.pikmin_bond: bool = False
        self.pikmin_bond_damage: float = 5.0
        self._bond_dead_last: Optional[int] = None  # reference deadPikis (par journee)
        # Reception : un DeathLink recu demande de tuer Olimar au prochain tick en jeu.
        self.pending_kill: bool = False
        # Empeche l'echo : une mort d'Olimar provoquee par un DeathLink recu ne
        # doit pas re-emettre un DeathLink (mode classic).
        self._suppress_orima_send: bool = False
        # Timestamps de nos propres DeathLink envoyes, pour filtrer nos morts qui
        # reviennent du serveur (le filtre de CommonClient ne garde que le dernier).
        self._sent_death_times: set = set()
        # Securite : un seul evenement DeathLink (envoi OU reception) par journee.
        # Verrouille apres le 1er evenement, rearme au debut de la journee suivante
        # (front montant de "dans un niveau"). Empeche toute cascade residuelle.
        self._deathlink_locked_this_day: bool = False
        self._in_level_prev: bool = False
        # Mode both : auto-mort d'Olimar en attente si non resolvable a l'envoi.
        self._pending_self_kill: bool = False
        # Traps recus via TrapLink (transitoires), en attente d'application en jeu.
        self.pending_trap_links: list = []
        self.pending_trap_link_sources: list = []  # #43 : parallele a pending_trap_links
        self._trap_source: Optional[str] = None     # #43 : joueur a l'origine du trap en cours
        # Traps recus en tant qu'items AP, deja appliques : {item_id: nb}.
        self.traps_applied: dict[int, int] = {}
        # Apres un End Day Trap : on suspend TOUTE application de trap jusqu'au
        # debut de la prochaine journee. Deux End Day Trap enchaines renvoyaient
        # le jeu au menu principal sans sauvegarde ; ce verrou l'empeche.
        self._traps_suspended_until_next_day: bool = False
        # Delai de grace en debut de journee : on saute quelques ticks de gameplay
        # actif avant d'appliquer un trap, pour ne pas en gaspiller un juste apres
        # l'atterrissage (Olimar pas encore vraiment operationnel).
        self._trap_grace_ticks: int = 0
        self._trap_free_since: Optional[float] = None  # #48
        # #5 : vrai tant qu'un ecran (pause, carte, texte...) couvre le gameplay ;
        # sert a rearmer le delai de grace a la fermeture du menu.
        self._trap_overlay_was_active: bool = False
        # Suivi de transition pour reinitialiser l'etat DeathLink par journee.
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
        # #4 : etat "deja applique" de chaque sauvegarde du jeu.
        try:
            self.game_saves = dict(Utils.persistent_load().get("pikmin_saves", {}).get(key, {}) or {})
        except Exception as e:
            self.game_saves = {}
            logger.debug(f"Could not load game saves: {e}")
        # Traps deja appliques (pour ne pas rejouer un trap au redemarrage).
        try:
            tdata = Utils.persistent_load().get("pikmin_traps", {}).get(self._save_key(), {})
            self.traps_applied = {int(k): v for k, v in tdata.items()}
        except Exception as e:
            logger.debug(f"Could not load applied traps: {e}")

    def save_applied(self) -> None:
        # Apres une deconnexion, reset_server_state() remet self.auth a None :
        # ecrire a ce moment creerait une entree parasite "applied_None_...".
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
        """#4 : persiste l'etat par sauvegarde du jeu (borne a MAX_TRACKED_SAVES)."""
        if not self.auth:
            return
        while len(self.game_saves) > MAX_TRACKED_SAVES:
            self.game_saves.pop(next(iter(self.game_saves)))
        try:
            Utils.persistent_store("pikmin_saves", self._save_key(), dict(self.game_saves))
        except Exception as e:
            logger.debug(f"Could not store game saves: {e}")

    def reset_server_state(self) -> None:
        """Repart d'un etat propre a chaque deconnexion.

        Sans ca, une reconnexion reutilisait le slot_data, les scouts et les
        hints de la session precedente, et la boucle de retry LocationScouts
        continuait d'emettre sur un socket ferme.
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
        # #37 : on construit l'UI Pikmin au-dessus de celle du parent (UI de
        # Universal Tracker avec son onglet si installe, sinon l'UI standard).
        from .P1UI import build_p1_ui
        return build_p1_ui(super().make_gui())

    # --- #38 : connexion seulement une fois le jeu detecte ---------------------
    async def connect(self, address: Optional[str] = None) -> None:
        """Ne lance la connexion qu'une fois Pikmin (ISO patchee) detecte dans
        Dolphin ; sinon l'adresse est mise en attente et dolphin_loop relance la
        connexion des la detection."""
        if not self.game_detected:
            self._pending_connect = address if address is not None else (self.server_address or "")
            lang = getattr(self, "detected_language", "en")
            logger.info("[Pikmin] " + WAIT_GAME_MSG.get(lang, WAIT_GAME_MSG["en"]))
            return
        await super().connect(address)

    async def server_auth(self, password_requested: bool = False) -> None:
        # Pattern standard des clients Archipelago : on ne delegue au parent que
        # pour la saisie du mot de passe, sinon il n'y a rien a faire.
        if password_requested and not self.password:
            # CommonContext directement : la version de UT enchaine elle-meme
            # get_username/send_connect, ce qui connecterait deux fois.
            await CommonContext.server_auth(self, password_requested)
        # #38 : nom du slot lu dans l'ISO patchee (sinon saisie manuelle).
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
            # Le seed_name AUTHENTIQUE ne figure que dans RoomInfo. On le stocke
            # ici, apres la garde de reconnexion de CommonClient (qui s'execute
            # avant on_package). L'ancien code le mettait a "unknown" depuis le
            # paquet Connected (qui n'a pas ce champ), donc la garde comparait
            # "unknown" au vrai seed a chaque reconnexion et bloquait tout.
            # En stockant la vraie valeur, la reconnexion compare seed==seed (OK)
            # et le dump de debug affiche enfin le bon seed.
            self.seed_name = args.get("seed_name") or self.seed_name
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

            # --- DeathLink / TrapLink : configurer les tags depuis slot_data ---
            self.death_link_mode = int(self.slot_data.get("death_link", 0))
            self.pikmin_death_amount = max(1, int(self.slot_data.get("pikmin_death_amount", 10)))
            self.trap_link_enabled = bool(self.slot_data.get("trap_link", 0))
            # Conversion des traps inter-jeux inconnus (defaut : activee).
            self.trap_link_conversion = bool(self.slot_data.get("trap_link_conversion", 1))
            # Pool de traps autorises pour la conversion : on ne garde que des
            # noms de traps Pikmin valides ; vide -> tous.
            allowed = self.slot_data.get("trap_link_conversion_traps", []) or []
            self.trap_link_conversion_traps = [n for n in allowed if n in TRAP_KINDS]
            self._orima_was_dead = False
            self._dead_pikis_baseline = None
            self._dead_pikis_sent = 0
            self.pending_kill = False
            # #3 Lien Olimar/Pikmin
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
            # TrapLink : un autre joueur a recu un trap et le diffuse. On applique
            # le meme trap chez nous. (DeathLink est deja gere par CommonClient.)
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
                    # TrapLink est INTER-JEUX : le nom vient du jeu emetteur. Si on
                    # ne le connait pas (ex. un trap de Hollow Knight), soit on le
                    # convertit en trap Pikmin aleatoire (convention TrapLink), soit
                    # on l'ignore selon l'option `trap_link_conversion`.
                    if not self.trap_link_conversion:
                        if self.debug_trap:
                            logger.info(f"[TrapLink] Unknown trap '{trap_name}' ignored "
                                        "(conversion disabled).")
                    else:
                        # Pool restreint par l'option (vide -> tous les traps Pikmin).
                        pool = self.trap_link_conversion_traps or [
                            n for n in TRAP_KINDS
                            # #7 : pas de Trip Trap si le trebuchement est retire du jeu.
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
                    # Nom deja connu (trap Pikmin) : applique tel quel, pas de conversion.
                    self.queue_trap_link(trap_name, source)
                    if self.debug_trap:
                        logger.info(f"[TrapLink] Trap '{trap_name}' queued for application.")

    async def send_death(self, death_text: str = "") -> None:
        """Envoie un DeathLink et memorise son timestamp.

        Le filtre anti-echo de CommonClient ne retient que le DERNIER timestamp
        envoye (last_death_link). Si on envoie plusieurs morts rapprochees, les
        precedentes reviennent du serveur et sont prises pour des morts recues
        -> re-declenchement en boucle (surtout en mode both). On memorise donc
        TOUS nos timestamps pour filtrer nos propres morts dans on_deathlink.
        """
        await super().send_death(death_text)
        self._sent_death_times.add(self.last_death_link)
        # Le message generique d'Archipelago ("Sending death to your friends...")
        # n'affiche pas la cause envoyee aux autres joueurs : on l'affiche aussi.
        if death_text and self.server and self.server.socket:
            logger.info(f"DeathLink: {death_text}")
        # Borne la memoire (les vieux timestamps ne reviendront plus).
        if len(self._sent_death_times) > 64:
            self._sent_death_times = set(sorted(self._sent_death_times)[-32:])

    def on_deathlink(self, data: dict) -> None:
        """DeathLink recu : planifie la mort d'Olimar, en ignorant nos propres morts."""
        if data.get("time") in self._sent_death_times:
            # C'est une de nos propres morts renvoyee par le serveur : ignorer.
            self.last_death_link = max(data["time"], self.last_death_link)
            return
        super().on_deathlink(data)
        self.pending_kill = True

    def queue_trap_link(self, trap_name: str, source: Optional[str] = None) -> None:
        """Place un trap recu via TrapLink dans la file d'application (surchargeable)."""
        self.pending_trap_links.append(trap_name)
        self.pending_trap_link_sources.append(source)  # #43 : joueur source

    async def send_trap_link(self, trap_name: str) -> None:
        """Diffuse aux autres joueurs TrapLink le trap qu'on vient de subir."""
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


def find_onion_containers(game: Game) -> dict[str, int]:
    """Localise les oignons vivants (GoalItem) par couleur.

    Remplace l'ancien scan RAM de 2 Mo. Reproduit `ItemMgr::getContainer()`
    de la decomp : on suit une chaine de pointeurs et on parcourt la liste
    chainee des creatures en filtrant sur mObjType == OBJTYPE_Goal.

        itemMgr -> mMeltingPotMgr -> mRootNode.mChild -> ... -> mNext
                -> mCreature (Creature*) -> GoalItem

    Retourne {couleur: adresse_du_GoalItem}. Dict vide si rien n'est charge
    (menu, transition), ce qui est un etat normal et non une erreur.
    """
    base_ptr = SYM_ITEM_MGR_PTR.get(game)
    if base_ptr is None:
        return {}

    C = ONION_CHAIN

    def deref(addr: int) -> int:
        """Lit un pointeur 32 bits et rejette tout ce qui n'est pas en MEM1/MEM2."""
        try:
            val = int.from_bytes(dme.read_bytes(addr, 4), "big")
        except Exception:
            return 0
        # Adresses GameCube/Wii valides uniquement -> evite de suivre du bruit.
        if 0x80000000 <= val < 0x81800000:
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

    # Garde-fou : liste chainee bornee, immunise contre un cycle ou de la
    # memoire a moitie initialisee pendant un chargement.
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


# fourCC (model ID) -> ap_id de la piece, pour identifier un Pellet in-game.
_MODELID_TO_AP_ID = {
    PART_MODEL_ID[name]: ALL_PARTS[name].ap_id
    for name in PART_MODEL_ID if name in ALL_PARTS
}

# ap_id -> zone/stage, pour reconstituer les compteurs PlayerState.
_APID_TO_STAGE = {
    data.ap_id: AREA_STAGE_ID[data.area]
    for data in ALL_PARTS.values() if data.area in AREA_STAGE_ID
}
# ap_id -> bit d'effet vaisseau (radar, jets).
_APID_TO_EFFECT = {
    ALL_PARTS[name].ap_id: bit
    for name, bit in SHIP_EFFECT_PARTS.items() if name in ALL_PARTS
}


def sync_playerstate_parts(ctx: P1Context, game: Game) -> None:
    """Reconcilie les compteurs de pieces de PlayerState avec les locations
    validees cote serveur, pour que les capacites (radar, jets) et les etoiles
    par niveau soient correctes meme pour des pieces collectees hors du jeu.

    Idempotent et jamais decroissant : on ne fait qu'ajouter des bits d'effet et
    remonter les compteurs au max, on n'ecrase jamais un total du jeu plus eleve.
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
        # Capacites du vaisseau (radar / jets) : OR des bits, idempotent.
        want_flag = 0
        for ap in checked_parts:
            want_flag |= _APID_TO_EFFECT.get(ap, 0)
        if want_flag:
            addr = ps + O["mShipEffectPartFlag"]
            cur = dme.read_byte(addr)
            if (cur | want_flag) != cur:
                dme.write_byte(addr, cur | want_flag)

        # Etoiles par niveau : nb de pieces validees par stage, sans decroitre.
        per_stage: dict[int, int] = {}
        for ap in checked_parts:
            st = _APID_TO_STAGE.get(ap)
            if st is not None:
                per_stage[st] = per_stage.get(st, 0) + 1
        base = ps + O["mStagePartsCollected"]
        for st, count in per_stage.items():
            a = base + st  # u8 par stage
            if dme.read_byte(a) < count:
                dme.write_byte(a, count)

        # Total de pieces (upgrade vaisseau, affichage) : au max.
        total = len(checked_parts)
        caddr = ps + O["mCurrParts"]
        cur_total = struct.unpack(">i", dme.read_bytes(caddr, 4))[0]
        if cur_total < total:
            dme.write_bytes(caddr, struct.pack(">i", total))
    except Exception:
        pass


def _detach_part_from_radar(game: Game, pellet: int) -> None:
    """Retire du radar l'icone d'une piece (replique RadarInfo::detachParts).

    Delie le noeud de mAlivePartsList dont mPart == pellet : sinon le radar
    continue d'afficher une icone pour une piece qu'on a fait disparaitre
    (MonoObjectMgr::kill ne declenche pas Creature::kill -> pas de detachParts).
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
            # Delier : relier le precedent (ou le slot de tete) au suivant.
            try:
                if prev:
                    dme.write_bytes(prev + R["NODE_NEXT"], struct.pack(">I", nxt))
                else:
                    dme.write_bytes(head_slot, struct.pack(">I", nxt))
                # Detacher le noeud + nettoyer son mPart.
                dme.write_bytes(node + R["NODE_NEXT"], struct.pack(">I", 0))
                dme.write_bytes(node + R["NODE_PART"], struct.pack(">I", 0))
            except Exception:
                pass
            return
        prev = node
        node = nxt


def despawn_collected_part_pellets(ctx: P1Context, game: Game) -> int:
    """Fait disparaitre les Pellets des pieces validees cote serveur.

    Les pellets sont geres par pelletMgr (un MonoObjectMgr), PAS par itemMgr.
    On enumere ses slots actifs (mEntryStatus[i] == 0), on repere les pellets de
    pieces de vaisseau (mObjType == OBJTYPE_Pellet et mConfig->mModelId connu),
    et si la location est deja validee cote serveur on les retire :
      - mIsAlive = 0 (invisible tout de suite) ;
      - mEntryStatus[i] = -2 -> MonoObjectMgr::update appelle kill() (retrait
        propre par le jeu au prochain update).
    Renvoie le nombre de pieces retirees.
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
        return v if 0x80000000 <= v < 0x81800000 else 0

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
        if status != 0:  # slot inactif
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
        # Piece validee cote serveur, encore presente : la retirer.
        try:
            # Retirer l'icone du radar (le kill du manager ne le fait pas).
            _detach_part_from_radar(game, creature)
            dme.write_byte(creature + P["PELLET_ISALIVE"], 0)
            dme.write_bytes(entry_status + i * 4, struct.pack(">i", ENTRYSTATUS_KILL))
            removed += 1
            if ctx.debug_hint:
                logger.info(f"[DEBUG] Pellet de pièce retiré "
                            f"(slot={i}, model={model_id!r}, ap_id={ap_id})")
        except Exception:
            pass

    return removed


# Taille de la zone objet balayee pour retrouver le fourCC de la piece qu'une
# creature contient. Verifie en jeu via /debugparts : l'UfoPartID n'est PAS au
# meme offset selon la classe (OBJTYPE_Snake : +0x31C ; OBJTYPE_Teki : +0x5D0),
# donc on balaye au lieu de coder un offset en dur. Lecture seule (identification).
_CREATURE_SCAN_LEN = 0x600


def _held_ufo_part_ap(obj: int) -> "Optional[int]":
    """ap_id de la piece CONTENUE par une creature affichee sur le radar, ou None.

    On balaye l'objet a la recherche du fourCC (ex. b'uf06') de la piece. Une
    creature ne contient qu'une piece : on ne renvoie un ap_id que si UN SEUL
    identifiant de piece connu est trouve (sinon ambigu -> None, par prudence).
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
    """Retire du radar les pieces validees cote serveur qui restent affichees
    parce qu'elles sont tenues A L'INTERIEUR d'un monstre/boss (issue #11).

    despawn_collected_part_pellets() ne traite que les slots ACTIFS du pelletMgr
    (mEntryStatus == 0). Quand une piece est contenue dans une creature, il n'y a
    meme PAS de Pellet dans le pelletMgr : le noeud radar pointe vers la CREATURE
    (mPart = OBJTYPE_Snake, etc.), qui memorise l'UfoPartID de la piece a
    +0x31C. Son icone restait donc sur le radar malgre la validation serveur.

    On part de la liste radar (mAlivePartsList) et on distingue deux cas :
      - noeud -> Pellet (piece libre encore listee) : on la tue proprement
        (mIsAlive = 0 + mEntryStatus = -2 via son slot) puis on delie le noeud ;
      - noeud -> Creature contenant une piece validee : on delie seulement le
        noeud radar (l'icone disparait). On NE touche PAS a la creature : si elle
        est tuee plus tard, elle lache un pellet deja collecte que la boucle
        classique retirera a son tour. Lecture seule pour l'identification.
    Renvoie le nombre d'icones retirees.
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
        return v if 0x80000000 <= v < 0x81800000 else 0

    radar = u32(ptr)
    if not radar:
        return 0

    known_models = _MODELID_TO_AP_ID

    # 1) Parcours LECTURE SEULE de la liste radar (sans la modifier ici).
    pellets_to_kill: list[int] = []   # pellets libres : kill + detach
    creatures_to_detach: list[int] = []  # creatures contenant une piece : detach seul
    node = u32(radar + R["ALIVE_CHILD"])
    for _ in range(128):  # garde-fou anti-boucle
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
                # Creature affichee sur le radar des pieces => elle contient une
                # piece. Son UfoPartID (fourCC) est memorise a un offset variable
                # selon la classe : on le retrouve en balayant l'objet.
                ap_id = _held_ufo_part_ap(obj)
                if ap_id is not None and ap_id in ctx.checked_locations and obj not in creatures_to_detach:
                    creatures_to_detach.append(obj)
        node = nxt

    if not pellets_to_kill and not creatures_to_detach:
        return 0

    # 2) Pour les pellets libres : localise chaque cible dans le pelletMgr (par
    #    pointeur) pour le tuer proprement via son slot, comme la boucle classique.
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

    # 3a) Pellets libres : icone radar + kill du pellet.
    for pellet in pellets_to_kill:
        try:
            _detach_part_from_radar(game, pellet)
            dme.write_byte(pellet + P["PELLET_ISALIVE"], 0)
            idx = slot_of.get(pellet)
            if idx is not None and entry_status:
                dme.write_bytes(entry_status + idx * 4, struct.pack(">i", ENTRYSTATUS_KILL))
            removed += 1
            if ctx.debug_hint:
                logger.info(f"[DEBUG] Pièce (pellet libre) retirée du radar "
                            f"pellet=0x{pellet:08X}, slot={idx}")
        except Exception:
            pass

    # 3b) Pieces contenues dans une creature : on delie seulement le noeud radar.
    for creature in creatures_to_detach:
        try:
            _detach_part_from_radar(game, creature)
            removed += 1
            if ctx.debug_hint:
                logger.info(f"[DEBUG] Icône de pièce retirée du radar (contenue dans "
                            f"un ennemi) creature=0x{creature:08X}")
        except Exception:
            pass

    return removed


async def handle_death_link(ctx: P1Context, game: Game) -> None:
    """DeathLink : detection (envoi) et application (reception).

    Modes (ctx.death_link_mode) :
      0 off, 1 classic, 2 pikmin, 3 both.
    Envoi :
      - classic / both : front montant de orimaDead (Olimar vient de mourir).
      - pikmin  / both : tous les X Pikmin morts dans la journee (deadPikis,
        deja remis a zero par journee).
      - both : en plus, quand le seuil de Pikmin est franchi, Olimar est aussi
        tue localement.
    Reception :
      - un DeathLink recu (ctx.pending_kill) tue Olimar au prochain tick en jeu.
    """
    # --- Auto-mort (mode both) : consequence de notre propre envoi, non soumise
    # au verrou. Retente si Olimar n'etait pas resolvable au moment de l'envoi.
    if ctx._pending_self_kill:
        if kill_olimar(game):
            ctx._pending_self_kill = False
            ctx._suppress_orima_send = True

    # --- Reception : tuer Olimar ---
    if ctx.pending_kill:
        if ctx._deathlink_locked_this_day:
            # Un evenement DeathLink a deja eu lieu cette journee : on ignore les
            # morts recues jusqu'au reset de debut de journee.
            ctx.pending_kill = False
        elif kill_olimar(game):
            ctx.pending_kill = False
            # La mort qui va suivre vient d'un DeathLink recu : ne pas la
            # renvoyer via la detection classic.
            ctx._suppress_orima_send = True
            ctx._deathlink_locked_this_day = True
            _lang = getattr(ctx, "detected_language", "en")
            logger.info(f"[Pikmin] {DEATHLINK_RECEIVED_MSG.get(_lang, DEATHLINK_RECEIVED_MSG['en'])}")
        # sinon : Olimar pas encore resolvable, on retente au prochain tick.

    if ctx.death_link_mode == 0:
        return

    # Verrou de securite : plus aucun envoi/reception tant que la journee n'a pas
    # ete reinitialisee (front montant "dans un niveau", voir dolphin_loop). On
    # continue de suivre l'etat de detection pour ne pas declencher un envoi
    # differe une fois le verrou leve.
    if ctx._deathlink_locked_this_day:
        ctx._orima_was_dead = read_orima_dead(game)
        dt = read_dead_pikis_total(game)
        if dt is not None:
            ctx._dead_pikis_last = dt
        return

    send_on_olimar = ctx.death_link_mode in (1, 3)   # classic, both
    send_on_pikmin = ctx.death_link_mode in (2, 3)   # pikmin, both
    pikmin_kills_olimar = ctx.death_link_mode == 3    # both

    # --- Envoi sur mort d'Olimar (front montant) ---
    if send_on_olimar:
        is_dead = read_orima_dead(game)
        if is_dead and not ctx._orima_was_dead:
            if ctx._suppress_orima_send:
                # Mort provoquee par un DeathLink recu (ou par le seuil pikmin en
                # mode both) : on la consomme sans re-emettre.
                ctx._suppress_orima_send = False
            else:
                await ctx.send_death(
                    f"{ctx.player_names.get(ctx.slot, 'Olimar')} was lost on the planet."
                )
                ctx._deathlink_locked_this_day = True
        ctx._orima_was_dead = is_dead
        if ctx._deathlink_locked_this_day:
            return

    # --- Envoi sur morts de Pikmin (tous les X, par journee) ---
    if send_on_pikmin:
        dead_total = read_dead_pikis_total(game)
        if dead_total is None:
            return
        # deadPikis est deja par journee, mais au tout debut de la journee il
        # peut encore etre RESIDUEL (pas remis a zero). A la 1re lecture (last
        # None), on prend la valeur courante comme reference deja comptee : sinon
        # un compte residuel serait pris pour des morts nouvelles et enverrait un
        # DeathLink en debut de journee. Une decroissance ulterieure = remise a
        # zero par le jeu -> on repart le comptage.
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
            await ctx.send_death(
                f"{ctx.player_names.get(ctx.slot, 'Olimar')} lost too many Pikmin."
            )
            ctx._deathlink_locked_this_day = True
            # Mode both : franchir le seuil tue aussi Olimar localement. C'est une
            # consequence de NOTRE envoi (pas une reception), donc on tue en ligne
            # meme si le verrou vient d'etre pose. Pas d'echo : _suppress_orima_send.
            if pikmin_kills_olimar:
                if kill_olimar(game):
                    ctx._suppress_orima_send = True
                else:
                    ctx._pending_self_kill = True  # Olimar pas resolvable, on reessaie


async def handle_pikmin_bond(ctx: P1Context, game: Game) -> None:
    """#3 Lien Olimar/Pikmin : chaque Pikmin mort retire des PV a Olimar.

    Source : GameStat::deadPikis (somme des 3 couleurs, remis a zero par
    journee). Comme pour le DeathLink "pikmin", la 1re lecture de la journee
    sert de reference (valeur residuelle possible) ; une baisse = remise a
    zero par le jeu -> nouvelle reference.

    A 0 PV (seuil de mort du jeu : <= 1.0), on passe par kill_olimar() pour
    declencher la VRAIE sequence de mort (ecrire mHealth seul ne suffit pas).
    La detection DeathLink classic enverra alors un DeathLink si active.
    Ne tourne que pendant le gameplay interactif (in_level_handlers).
    """
    if not ctx.pikmin_bond:
        return
    dead_total = read_dead_pikis_total(game)
    if dead_total is None:
        return
    last = ctx._bond_dead_last
    ctx._bond_dead_last = dead_total
    if last is None or dead_total <= last:
        return  # reference / remise a zero / rien de nouveau
    if read_orima_dead(game):
        return  # deja a terre : rien a retirer

    navi = _resolve_olimar(game)
    if navi is None:
        # Olimar pas resolvable : on garde l'ancienne reference pour
        # appliquer ces morts au prochain tick.
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
        logger.info(f"[DEBUG BOND] {deaths} Pikmin mort(s) : PV {h:.1f} -> {max(new, 0.0):.1f}")
    if new <= 1.0:
        # Mort d'Olimar par le lien : sequence de mort reelle du jeu.
        if kill_olimar(game):
            ctx._client_kill_reason = "Pikmin Bond"
            await report_client_kill(ctx)
    else:
        try:
            dme.write_bytes(addr, struct.pack(">f", new))
        except Exception as e:
            logger.debug(f"Error writing bond damage: {e}")


OLIMAR_MAX_HEALTH = 100.0


async def handle_olimar_bond(ctx: P1Context, game: Game) -> None:
    """#44 Olimar Bond : chaque Pikmin ne soigne Olimar (olimar_bond_heal % de
    sa sante max, plafonnee a 100).

    Source : GameStat::bornPikis ("germes aujourd'hui"), qui compte les graines
    sorties des oignons ET, depuis #33, les bonus Pikmin recus (en journee, ou
    au debut de la journee suivante s'ils arrivent sur la carte). Comme pour le
    lien Olimar/Pikmin : 1re lecture de la journee = reference, une baisse =
    remise a zero par le jeu.
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
        ctx._olimar_bond_last = last  # on reessaie au prochain tick
        return
    heal = OLIMAR_MAX_HEALTH * float(slot_data.get("olimar_bond_heal", 1)) / 100.0 * (born - last)
    addr = navi + NAVI_CHAIN["CREATURE_HEALTH"]
    try:
        h = struct.unpack(">f", dme.read_bytes(addr, 4))[0]
        if h <= 1.0:
            return  # deja a terre : pas de resurrection
        new = min(OLIMAR_MAX_HEALTH, h + heal)
        if new > h:
            dme.write_bytes(addr, struct.pack(">f", new))
            if ctx.debug_trap:
                logger.info(f"[DEBUG BOND] {born - last} Pikmin ne(s) : PV {h:.1f} -> {new:.1f}")
    except Exception as e:
        logger.debug(f"olimar bond: {e}")


# id d'item de trap -> type interne, construit une fois.
_TRAP_ID_TO_KIND = {TRAP_ITEMS[name]: TRAP_KINDS[name] for name in TRAP_ITEMS}
_TRAP_KIND_TO_NAME = {TRAP_KINDS[name]: name for name in TRAP_ITEMS}


async def handle_traps(ctx: P1Context, game: Game) -> None:
    """Applique les traps recus (items AP) et ceux recus via TrapLink.

    Un trap a la fois par tick. Les traps-items sont persistes (traps_applied)
    pour ne pas etre rejoues au redemarrage ; les traps TrapLink sont
    transitoires (file pending_trap_links).
    """
    # On n'applique AUCUN trap tant que la journee n'a pas vraiment commence :
    # au choix du niveau, pendant le chargement et pendant la cinematique d'intro,
    # le joueur ne controle pas Olimar (mIsPauseAllowed FALSE). On exige aussi
    # qu'Olimar soit resolvable. Les traps recus a ce moment restent en attente
    # (items_received / pending_trap_links) et s'appliqueront une fois la journee
    # reellement en cours.
    if not is_day_active(game) or _resolve_olimar(game) is None:
        return

    # Verrou post-End-Day-Trap : aucun trap tant que la prochaine journee n'a pas
    # commence (leve au front montant de "dans un niveau", cf. dolphin_loop).
    if ctx._traps_suspended_until_next_day:
        return

    # #5 : menu Pause / carte / fenetre de texte / menu d'oignon ouvert -> on
    # suspend tout (traps AP et TrapLink restent en file). A la fermeture, on
    # rearme un delai de grace (~3 s) avant d'appliquer le trap en attente.
    if is_overlay_active(game):
        ctx._trap_overlay_was_active = True
        ctx._trap_free_since = None
        return
    # #48 : comme les cones (#46), aucun trap pendant une cinematique, puis
    # CONE_START_DELAY secondes de jeu libre (fin de la cinematique de debut de
    # journee comprise) avant d'appliquer le premier trap.
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
            logger.info("[DEBUG TRAP] Menu ferme : traps reprennent apres le delai de grace.")

    # Delai de grace en tout debut de journee (gameplay actif) : evite de gaspiller
    # un trap juste apres l'atterrissage.
    if ctx._trap_grace_ticks > 0:
        ctx._trap_grace_ticks -= 1
        return

    # 1) Traps recus comme items AP.
    for item in ctx.items_received:
        item_id = item.item
        kind = _TRAP_ID_TO_KIND.get(item_id)
        if kind is None:
            continue
        total = sum(1 for i in ctx.items_received if i.item == item_id)
        already = ctx.traps_applied.get(item_id, 0)
        if total <= already:
            continue
        # #43 : joueur qui a envoye CE trap (la (already+1)-ieme occurrence).
        occ = [i for i in ctx.items_received if i.item == item_id][already]
        ctx._trap_source = (ctx.player_names.get(occ.player)
                            if getattr(occ, "player", ctx.slot) != ctx.slot else None)
        if await apply_trap(game, kind, ctx):
            ctx.traps_applied[item_id] = already + 1  # un a la fois
            ctx.save_applied()
            name = _TRAP_KIND_TO_NAME.get(kind, kind)
            if ctx.debug_trap:
                logger.info(f"[DEBUG TRAP] Trap applied: {name}")
            # TrapLink : diffuser le trap qu'on vient de subir aux autres.
            if ctx.trap_link_enabled:
                await ctx.send_trap_link(name)
            # End Day Trap : la journee va se terminer ; on gele les traps
            # jusqu'a la prochaine pour ne pas en appliquer un 2e dans la fenetre
            # de fin de journee (ce qui renvoyait au menu sans sauvegarde).
            if kind == "end_day":
                ctx._traps_suspended_until_next_day = True
            return  # un seul trap par tick

    # 2) Traps recus via TrapLink (transitoires).
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
        # sinon : pas applicable maintenant, on retentera au prochain tick.


# --- #4 Custom Save -----------------------------------------------------------
#
# Probleme : l'etat "bonus Pikmin deja appliques" etait stocke uniquement cote
# client (_persistent_storage.yaml, par slot AP). Nouvelle partie, autre slot de
# sauvegarde du jeu (A/B/C) ou rechargement d'une sauvegarde anterieure : les
# bonus n'etaient jamais reappliques (ou l'etat ne correspondait plus au jeu).
#
# La sauvegarde du jeu n'a pas de place libre exploitable (seul PlayerState::_186
# est sauvegarde sans etre utilise, et c'est un bool normalise a 0/1 au
# chargement). On identifie donc chaque sauvegarde par son checksum
# (gameflow.mSaveGameCrc) : il est lu depuis la carte au choix du fichier et
# recalcule a chaque sauvegarde. Le client memorise, pour chaque checksum,
# les bonus appliques AU MOMENT de cette sauvegarde :
#   - chargement d'un fichier (CardSelect -> jeu) :
#       * nouvelle partie (mSavedDay == 1)   -> rien d'applique : tout est reapplique ;
#       * checksum connu                    -> etat de cette sauvegarde (les bonus
#                                               appliques puis non sauvegardes seront
#                                               reappliques) ;
#       * checksum inconnu (save anterieure a cette version) -> etat actuel conserve.
#   - sauvegarde (checksum qui change en jeu) -> on enregistre l'etat courant.
# Copier un fichier vers un autre slot donne le meme checksum : l'etat suit.

_ONEPLAYER_CARD_SELECT = 1
_ONEPLAYER_INTRO_GAME = 5
_SAVE_TRACK_SUBSECTIONS = (_ONEPLAYER_INTRO_GAME, ONEPLAYER_MAP_SELECT, ONEPLAYER_NEW_PIKI_GAME)
# #32 : sous-sections ou les handlers "always" peuvent ecrire en RAM.
_STORY_SUBSECTIONS = (_ONEPLAYER_CARD_SELECT, _ONEPLAYER_INTRO_GAME, ONEPLAYER_MAP_SELECT, ONEPLAYER_NEW_PIKI_GAME)
MAX_TRACKED_SAVES = 60

# Messages par langue du jeu detectee (comme SYNC_ACTIVE_MSG).
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
    """#4 : suit chargements et sauvegardes du jeu (voir bloc ci-dessus)."""
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
                # Un fichier vient d'etre choisi (nouvelle partie ou chargement).
                # Nouvelle partie = PlayState.mSavedDay == 1 : un fichier vierge
                # garde le jour 1 de PlayState::Initialise, alors que toute
                # sauvegarde a lieu apres le passage au jour suivant (>= 2).
                # (mSaveStatus n'est PAS fiable : CardSelect le passe a
                # ReadyToSave des qu'un fichier vierge est choisi.)
                try:
                    saved_day = dme.read_byte(gf["PLAYSTATE_SAVED_DAY"])
                except Exception:
                    saved_day = None
                slot = _read_u32_opt(gf["FILE_SLOT"])
                if ctx.debug_pbonus:
                    logger.info(f"[DEBUG] Fichier choisi : crc={crc:08X} savedDay={saved_day} slot={slot}")
                ctx._pending_save_load = (crc, saved_day == 1,
                                          (slot + 1) if slot is not None and slot < 3 else "?")
                ctx._save_crc = crc
            elif ctx._save_crc is None:
                # Client demarre (ou reconnecte) en cours de partie : continuation.
                ctx._save_crc = crc
            elif crc != ctx._save_crc:
                # Le jeu vient de sauvegarder : on fige l'etat pour ce checksum.
                ctx._save_crc = crc
                if connected and ctx._pending_save_load is None:
                    key = f"{crc:08X}"
                    ctx.game_saves.pop(key, None)  # re-insere en fin (plus recent)
                    ctx.game_saves[key] = {str(k): v for k, v in ctx.pikmin_items_applied.items()}
                    ctx.store_game_saves()
                    if ctx.debug_pbonus:
                        logger.info(f"[DEBUG] Sauvegarde du jeu {key} : etat des bonus enregistre.")

    # Resolution du chargement (attend la connexion au serveur si besoin).
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


# --- #33 : bonus Pikmin comptes comme "germes" --------------------------------
_BORN_COLOR_INDEX = {"blue": 0, "red": 1, "yellow": 2}  # ColCounter / PikiNum


def _add_born_pikis(game: Game, color: str, amount: int) -> bool:
    """GameStat::bornPikis[color] += amount ("germes aujourd'hui").

    A la fin de la journee, le jeu ajoute lui-meme bornPikis a
    PlayerState::mSproutedNum ("total germes") et au record global
    (updateFinalResult) : pas besoin d'ecrire ces cumuls nous-memes.
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
    """Met a jour le point de l'heure courante du graphique de population
    (PlayerState::mPerHourGraph) avec GameStat::allPikis, comme le fait
    PlayerState::update() a chaque changement d'heure. Sans ca, un bonus recu
    n'apparaissait qu'a l'heure suivante (ou jamais, si la journee se
    terminait dans la meme heure)."""
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
    """Compte comme germes du jour les bonus recus hors journee (carte du monde,
    entre deux journees), une fois la nouvelle journee reellement commencee
    (GameStat est remis a zero au chargement du niveau)."""
    if not any(ctx._pending_born.values()):
        return
    if not (is_in_level(game) and is_day_active(game)):
        return
    for color, n in ctx._pending_born.items():
        if n and _add_born_pikis(game, color, n):
            ctx._pending_born[color] = 0
            if ctx.debug_pbonus:
                logger.info(f"[DEBUG] bornPikis {color} +{n} (bonus recu hors journee)")


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
    # #4 : fichier juste charge, etat pas encore resolu -> on attend.
    if ctx._pending_save_load is not None:
        return
    # #33 : bonus recus hors journee -> "germes" de la journee en cours.
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

    # Offsets reels dans GoalItem : mHeldPikis[Leaf/Bud/Flower] a _0x42C.
    # (L'ancien code utilisait +0x10/+0x14/+0x18, un point d'ancrage arbitraire
    #  issu du scan ; la decomp donne l'offset exact du membre.)
    _HELD = ONION_CHAIN["GOAL_HELDPIKIS"]
    DYN_OFFSETS = {"leaf": _HELD + 0x0, "bud": _HELD + 0x4, "flower": _HELD + 0x8}
    DYN_BASE_CACHE = {"red": "_dyn_base_red", "yellow": "_dyn_base_yellow", "blue": "_dyn_base_blue"}

    # Resolution des oignons par chaine de pointeurs (ex-scan RAM de 2 Mo).
    # Assez peu couteux pour etre refait a chaque debut de journee ; les objets
    # sont realloues a chaque chargement, donc on ne conserve jamais un cache
    # d'un jour sur l'autre.
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
    # #32 : n'ecrire dans l'oignon VIVANT (objet de tas, DYN) que pendant le
    # gameplay interactif. Pendant une cinematique EN NIVEAU (intro de journee,
    # et surtout la sequence de fin declenchee par le goal) l'objet est demonte
    # / reutilise par le rendu : y ecrire corrompait le flux GPU (Dolphin :
    # "GFX FIFO opcode inconnu 0xf6"). La persistance passe de toute facon par
    # STAGE (source de verite), inchangee.
    in_game = (not ctx._onion_dyn_was_zero) and (current_day != 0) and is_day_active(game)

    def add_pikmin(color: str, stage: str, amount: int) -> bool:
        """Applique un bonus. Renvoie toujours True : le compteur persistant
        (STAGE) est la source de verite et doit toujours etre incremente
        immediatement, que l'oignon de cette couleur soit ou non charge en
        memoire en ce moment (il ne l'est que si on est physiquement dans la
        zone qui le contient — jamais sur la carte du monde, par exemple).

        Avant ce fix, tant que l'oignon n'etait pas resolu, l'ecriture STAGE
        elle-meme etait sautee (pas seulement la sync visuelle DYN) : le
        bonus restait en attente indefiniment, sans jamais apparaitre dans le
        total tant que le jeu ne le resynchronisait pas lui-meme au
        changement de journee suivant. Le compteur affiche (HUD bas-droite,
        ecran de resultats) semblait alors "en retard d'un jour".

        La synchronisation live dans l'oignon vivant (DYN, mHeldPikis) reste
        tentee en best-effort quand on est en jeu et que l'oignon est
        resolu, pour un rendu instantane sans attendre le jour suivant, mais
        son echec ne doit plus jamais empecher ni retarder l'ecriture STAGE.
        """
        s_addr = stage_addrs[color][stage]
        old_s = read_u32(s_addr)
        write_u32(s_addr, old_s + amount)
        if ctx.debug_pbonus:
            logger.info(
                f"[DEBUG] STAGE 0x{s_addr:08X} {color}/{stage} : {old_s} -> {old_s + amount} (+{amount})"
            )

        # GameStat::containerPikis et GameStat::allPikis (par couleur, tous
        # stades confondus) : ce sont EUX qui alimentent le total HUD affiche
        # en temps reel (mTotalPikiNum) et l'ecran de resultats. Sans cette
        # ecriture, le total visible n'augmente jamais sur le coup : il fallait
        # attendre que le jeu refasse lui-meme ce calcul, ce qui n'arrive
        # qu'au chargement du jour suivant.
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

        # #33 : le bonus compte comme des Pikmin "germes" (ecran de fin de
        # journee : germes aujourd'hui + total germes) et apparait tout de suite
        # dans le graphique de population. Hors journee (carte du monde...),
        # GameStat sera remis a zero au prochain chargement : on met en attente
        # et flush_pending_born() l'ajoute au debut de la journee suivante.
        if in_game and is_in_level(game):
            if not _add_born_pikis(game, color, amount):
                ctx._pending_born[color] += amount
            _update_population_graph(game)
        else:
            ctx._pending_born[color] += amount

        if in_game and stage in DYN_OFFSETS:
            base = getattr(ctx, DYN_BASE_CACHE.get(color, ""), None)
            if not base:
                # Oignon pas encore charge (pas dans cette zone) : on retente
                # la resolution, mais on ne bloque plus la-dessus.
                base = find_onion_containers(game).get(color)
                if base:
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
        # On ne marque l'item applique QUE si l'ecriture a durablement abouti.
        # Sinon on le laisse en attente : il sera re-tente au prochain tick, une
        # fois l'oignon resolu. Evite de perdre des Pikmin recus.
        if add_pikmin(color, stage, bonus):
            ctx.pikmin_items_applied[item_id] = total_received

    ctx.save_applied()


async def _create_super_radar_hint(ctx: P1Context, part_name: str) -> None:
    """Cree le hint Super Radar (emplacement de la piece du joueur) pour part_name.

    Reutilise les hints de slot_data (comme handle_ship_part_hints). Sans effet si
    aucun hint n'est disponible ou s'il a deja ete cree.
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
        logger.info(f"[DEBUG] Super Radar hint créé pour {part_name} "
                    f"(pièce collectée côté serveur)")


async def handle_parts(ctx: P1Context, game: Game):
    slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
    hint_mode = slot_data.get("ship_part_hint_mode", 0)

    # Fait disparaitre physiquement du niveau les pieces validees cote serveur
    # (ex. autre jeu termine) et non ramassees en jeu. Un seul parcours par tick.
    despawn_collected_part_pellets(ctx, game)
    # Meme chose pour les pieces tenues A L'INTERIEUR d'un monstre/boss, que la
    # boucle ci-dessus ignore (slot pelletMgr non actif) : on part de la liste
    # radar pour retirer leur icone et les tuer (issue #11).
    despawn_collected_parts_on_radar(ctx, game)
    # Met a jour capacites du vaisseau (radar/jets) et etoiles par niveau pour
    # les pieces validees cote serveur (que le jeu n'a pas enregistrees).
    sync_playerstate_parts(ctx, game)

    for name, data in ALL_PARTS.items():
        addr = data.memory_address[game]
        try:
            read = dme.read_byte(addr)
        except Exception:
            continue

        # Sens normal : collectee en jeu -> on envoie le check au serveur.
        if read == data.collected_byte and data.ap_id not in ctx.checked_locations:
            ctx.locations_checked.add(data.ap_id)
            await ctx.check_locations([data.ap_id])

        # Sens inverse : la location est validee cote serveur (ex. !collect,
        # autre jeu termine) mais la piece n'est pas collectee en jeu -> on ecrit
        # l'octet "collectee" pour qu'elle disparaisse physiquement du niveau.
        elif data.ap_id in ctx.checked_locations and read != data.collected_byte:
            try:
                dme.write_byte(addr, data.collected_byte)
            except Exception:
                continue
            if ctx.debug_hint:
                logger.info(f"[DEBUG] Pièce {name} auto-collectée (validée côté serveur)")
            # Hint de l'emplacement de la piece si Super Radar / Both.
            if hint_mode in (2, 3):
                await _create_super_radar_hint(ctx, name)


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
# Issue #12 : rafraichissement EN PLACE de la carte du monde (story mode).
#
# Adresses/offsets verifies dans la decomp projectPiki/pikmin :
#   src/plugPikiColin/mapSelect.cpp       -> static zen::DrawWorldMap* mapWindow
#   include/zen/DrawWorldMap.h            -> offsets DrawWorldMap
#   src/plugPikiYamashita/drawWorldMap.cpp-> WorldMapCoursePointMgr / CoursePoint
#
# La carte fige la visibilite des zones et le compteur de pieces a l'ouverture
# (constructeur de DrawWorldMap ; WorldMapCoursePointMgr::init lit courseOpen()).
# Rien ne les reevalue tant qu'on reste dessus -> si une piece/zone arrive
# pendant qu'on est sur la carte, la zone reste invisible et le compteur fige.
#
# On corrige sans patch DOL, via le static mapWindow :
#   - compteur : mCurrentPartsNum est relu chaque frame par un NumberPicCallBack,
#     le reecrire met le compteur a jour immediatement ;
#   - zones : pour une zone debloquee dont le course point n'est pas encore
#     visible, on met mIsVisible = 1 (selectionnable) et on declenche l'animation
#     de revelation (mMode=Appear + point.mAppearState=RocketIncoming), exactement
#     comme le jeu lors d'un vrai deblocage (DrawWorldMap::start -> appear()).
# Adresses/offsets : cf. SYM_MAP_WINDOW_PTR / MAP_GAME2SCR / WORLDMAP_CHAIN dans
# P1Symbols.py (generes et maintenus par gen_symbols.py depuis la decomp).
# #40 : WorldMapCoursePoint.mLinkPoints (_2C), indexe par linkFlag
# (src/plugPikiYamashita/drawWorldMap.cpp : Up 0, Down 1, Left 2, Right 3).
CP_LINKPOINTS = 0x2C
# #45 : DrawWorldMap.mTotalPikiCounts[3] (Blue, Red, Yellow).
DWM_PIKI_COUNTS = 0x44


# #40 : liens du curseur quand TOUTES les zones sont ouvertes (index ecran),
# repris de WorldMapCoursePointMgr::init (branche courseOpen(Distant Spring)).
# scr : 0 Distant Spring, 1 Forest of Hope, 2 Impact Site, 3 Forest Navel,
# 4 Final Trial. Ordre des liens : Up, Down, Left, Right.
WORLDMAP_FULL_LINKS = (
    (4, 1, None, 3),       # 0 Distant Spring
    (0, None, None, 2),    # 1 Forest of Hope
    (3, None, 1, None),    # 2 Impact Site
    (4, 2, 0, None),       # 3 Forest Navel
    (None, 3, 0, None),    # 4 Final Trial
)


# Variante du jeu quand Distant Spring (scr 0) est ferme : Forest of Hope
# monte vers Forest Navel et Forest Navel va a gauche vers Forest of Hope.
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
    """Zone ouverte la plus proche au-dela de t (t ferme), en traversant les
    zones fermees de la carte complete."""
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
    """Liens du curseur pour un ensemble quelconque de zones ouvertes.

    1. Base = exactement la table du jeu (variante selon Distant Spring ouvert),
       donc aucun changement dans les cas d'origine.
    2. Tant qu'une zone ouverte ne peut pas atteindre une autre zone ouverte
       (deblocage dans un ordre inhabituel, ex. Impact Site + Distant Spring),
       une direction qui mene a une zone FERMEE est redirigee vers la zone
       ouverte la plus proche au-dela. Les liens valides ne sont jamais touches.
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
    """Reecrit mLinkPoints des 5 zones selon les zones visibles (#40)."""
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
    """Rafraichit la carte du monde en place quand une piece/zone arrive alors
    que le joueur y est deja (issue #12). Sans effet hors carte du monde."""
    ptr_addr = SYM_MAP_WINDOW_PTR.get(game)
    if ptr_addr is None:
        return
    # Uniquement sur la carte du monde : sinon mapWindow (static jamais remis a
    # zero) peut pointer un objet libere.
    if _oneplayer_subsection(game) != ONEPLAYER_MAP_SELECT:
        return
    try:
        wm = struct.unpack(">I", dme.read_bytes(ptr_addr, 4))[0]
    except Exception:
        return
    if not (_RAM_MIN <= wm < _RAM_MAX):
        return  # pas de carte du monde (mode challenge, ou pas encore construite)

    W = WORLDMAP_CHAIN
    try:
        # --- compteur de pieces (bas-gauche) : relu chaque frame ---
        cur_addr = wm + W["DWM_CURRPARTS"]
        if struct.unpack(">i", dme.read_bytes(cur_addr, 4))[0] != ship_parts_count:
            dme.write_bytes(cur_addr, struct.pack(">i", ship_parts_count))

        # --- #45 : compteurs de Pikmin par couleur (haut de la carte) ----------
        # DrawWorldMap.mTotalPikiCounts[Blue/Red/Yellow] (_44) : rempli une seule
        # fois a l'ouverture de la carte (PlayerState::getTotalPikiCount =
        # pikiInfMgr, total des stades) mais relu a chaque frame par l'affichage.
        # On le recalcule depuis les compteurs STAGE (ou arrivent les bonus).
        stage_addrs = ONION_STAGE_ADDRS_CLIENT.get(game, {})
        for color, idx in (("blue", 0), ("red", 1), ("yellow", 2)):
            stages = stage_addrs.get(color)
            if not stages:
                continue
            total = sum(struct.unpack(">i", dme.read_bytes(a, 4))[0] for a in stages.values())
            cnt_addr = wm + DWM_PIKI_COUNTS + idx * 4
            if struct.unpack(">i", dme.read_bytes(cnt_addr, 4))[0] != total:
                dme.write_bytes(cnt_addr, struct.pack(">i", total))

        # --- #40 : liens de navigation du curseur ---------------------------
        # WorldMapCoursePointMgr::init() calcule les liens haut/bas/gauche/droite
        # UNE fois, a l'ouverture de la carte, et ne gere qu'un cas : Distant
        # Spring ouvert ou non. Une zone revelee en direct (#12) restait donc
        # inaccessible au curseur, et un futur ordre de deblocage melange (ex.
        # Impact Site + Distant Spring seulement) ne serait pas navigable du
        # tout. On recalcule donc les liens a partir des zones REELLEMENT
        # visibles (mIsVisible), independamment de l'ordre de deblocage.
        _relink_worldmap(wm)

        # --- zones : on ne revele que si la carte est en mode Operation (idle),
        #     pour ne pas perturber un dialogue de confirmation / le journal.
        if struct.unpack(">i", dme.read_bytes(wm + W["DWM_CURRENTMODE"], 4))[0] != DWM_MODE_OPERATION:
            return
        mgr = struct.unpack(">I", dme.read_bytes(wm + W["DWM_COURSEPOINTMGR"], 4))[0]
        if not (_RAM_MIN <= mgr < _RAM_MAX):
            return

        # Memes seuils que les bits UNLOCKED_AREAS ci-dessus.
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
                    continue  # deja visible -> idempotent
            except Exception:
                continue
            # Rendre selectionnable + jouer l'animation de revelation.
            dme.write_byte(point + W["CP_ISVISIBLE"], 1)
            dme.write_bytes(point + W["CP_APPEARSTATE"], struct.pack(">i", CP_APPEAR_START))
            dme.write_bytes(point + W["CP_APPEARTIMER"], struct.pack(">f", 0.0))
            triggered = True
            if getattr(ctx, "debug_hint", False):
                logger.info(f"[DEBUG] Carte : zone {game_area} revelee en place "
                            f"(scr={MAP_GAME2SCR[game_area]})")
        if triggered:
            dme.write_bytes(mgr + W["CPM_MODE"], struct.pack(">i", CPM_MODE_APPEAR))
    except Exception as e:
        logger.debug(f"[Pikmin] refresh worldmap: {e}")


def _write_playerstate_part_counts(game: Game, total: int, required: int) -> None:
    """#32 : ecrit l'octet de poids faible de PlayerState.mCurrParts (_17C) et
    mRequiredUfoPartCount (_180). Les anciennes adresses fixes (PAL 0x812427FF /
    0x81242803, NTSC 0x81249DE7 / 0x81249DEB) etaient ces memes champs, mais
    supposaient playerState toujours a la meme adresse de tas."""
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


def is_final_ending(game: Game) -> bool:
    """#32 : vrai pendant la sequence de fin (fin de la derniere journee avec
    30 pieces : decollage, oignons, Olimar dans l'espace). Le jeu y reinitialise
    les tas Teki/Movie pour les cinematiques ; le client ne doit plus rien ecrire."""
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

    # #32 : mCurrParts / mRequiredUfoPartCount ecrits via le pointeur
    # playerState (et non plus a une adresse de tas codee en dur), et seulement
    # si la valeur change.
    _write_playerstate_part_counts(game, ship_parts_count, total_required)
    if dme.read_byte(UNLOCKED_AREAS[game]) != areas:
        dme.write_byte(UNLOCKED_AREAS[game], areas)

    # Stage visuel du S.S. Dolphin (issue #8). Le jeu ne recalcule
    # mShipUpgradeLevel qu'a l'interieur de PlayerState::registerPart(),
    # jamais automatiquement a partir du nombre de pieces : comme les checks
    # AP contournent cette fonction (pieces marquees collectees directement
    # en memoire), le vaisseau ne changeait jamais visuellement de stage.
    # Memes seuils que le jeu (verifies dans la decomp, et deja utilises
    # ci-dessus pour debloquer les zones).
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
                # Jamais decroissant : ne pas retrograder le visuel si, pour
                # une raison quelconque, ship_parts_count redescend un tick.
                if dme.read_byte(addr) < ship_upgrade_level:
                    dme.write_byte(addr, ship_upgrade_level)
        except Exception as e:
            logger.debug(f"Error writing mShipUpgradeLevel: {e}")

    # Issue #12 : si on est deja sur la carte du monde, rafraichir les zones
    # debloquees et le compteur de pieces sans avoir a ressortir/relancer un jour.
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
    """QOL 'Normal First Day' : efface PlayerState.mIsTutorialMode.

    Tant que ce flag vaut 1, le jeu traite le jour 1 comme un tutoriel : intro du
    crash (DEMOID_OlimarWakeUp au lieu de l'atterrissage normal), horloge figee et
    pop-ups scriptes. Le forcer a 0 des qu'une sauvegarde est chargee rend le jour 1
    classique. Le jour 1 charge le niveau sans passer par la carte du monde, donc on
    l'efface a chaque tick (tres tot) et on continue de le corriger si l'intro est
    passee avant notre premier tick.
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
    """Marque une liste d'index EDemoFlags comme deja vus dans le bitset RAM."""
    for idx in indices:
        byte_addr = stored + (idx >> 3)
        cur = dme.read_byte(byte_addr)
        bit = 1 << (idx & 7)
        if not (cur & bit):
            dme.write_byte(byte_addr, cur | bit)


async def handle_qol_skip_cutscenes(ctx: P1Context, game: Game) -> None:
    """QOL : saute les cinematiques/textes listes dans l'OptionSet 'skip_events',
    en marquant leurs DemoFlags comme deja vus (mStoredFlags = u8[32] pointe par
    PlayerState+0x5C ; bit du flag i = mStoredFlags[i>>3] & (1 << (i & 7))).

    Cas special "Onion Discovery" : sauter la decouverte prive aussi le jeu de
    l'activation (boot) et de l'enregistrement (suivi + affichage) de l'oignon.
    On repare via mContainerFlag + mDisplayPikiFlag :
      * bits boot (y) actives pour toutes les couleurs (oignon actif au spawn) ;
      * bit suivi (x) + bit affichage active pour l'oignon reellement accede par
        Olimar (navi->mGoalItem), pas a la simple arrivee dans la zone.
    ("Part Collection" et "Ship Upgrade" sont des patches DOL, appliques au patch.)
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

        # Pre-marque les DemoFlags de toutes les entrees selectionnees.
        flags = []
        for key in skips:
            flags.extend(SKIP_EVENT_DEMOFLAGS.get(key, ()))
        if flags:
            _set_demo_flags(stored, flags)

        # Reparation onion (suivi + affichage) si sa decouverte est sautee.
        if "Onion Discovery" in skips:
            cf_addr = ps + PLAYERSTATE_OFFSETS["mContainerFlag"]
            cf = dme.read_byte(cf_addr)
            new_cf = cf | CONTAINER_BOOT_ALL
            if (new_cf & 0x07) != 0x07:  # un bit de suivi manque encore
                navi = _resolve_olimar(game)
                if navi:
                    goal = struct.unpack(">I", dme.read_bytes(navi + NAVI_CHAIN["NAVI_GOALITEM"], 4))[0]
                    # On NE pose hasContainer QUE si mGoalItem pointe vraiment sur
                    # un onion vivant (mObjType == OBJTYPE_Goal). Un pointeur
                    # perime donnerait une couleur erronee -> hasContainer d'une
                    # couleur sans onion present -> null->refresh() a la fin de
                    # journee (cinematique d'envol d'onion) -> crash.
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

            # mDisplayPikiFlag doit couvrir les memes couleurs que le suivi (x),
            # sinon les onions possedes/compteurs manquent dans la carte du monde
            # et le resume de fin de journee. Bits identiques (1<<couleur).
            owned = new_cf & 0x07
            df_addr = ps + PLAYERSTATE_OFFSETS["mDisplayPikiFlag"]
            df = dme.read_byte(df_addr)
            if (df | owned) != df:
                dme.write_byte(df_addr, df | owned)
    except Exception:
        pass


# --- #34 : rayon de lumiere (cone) sous l'oignon ------------------------------
# GoalItem (include/GoalItem.h) :
#   _3F6 bool mIsClosing         _3F8 f32 mConeSizeTimer
#   _3FC Vector3f echelle pleine du cone
#   _408 bool mIsConeEmit        _40C EffShpInst* mSpotModelEff (mSRT.s @ +0x14)
# Un oignon pas encore decouvert est charge avec un cone (et une echelle de
# reference) a 0 ; seule la cinematique de decouverte le fait apparaitre. Avec
# "Onion Discovery" sautee, le rayon manquait donc jusqu'au lendemain.
GOAL_IS_CLOSING = 0x3F6
GOAL_CONE_TIMER = 0x3F8
GOAL_CONE_FULL_SCALE = 0x3FC
GOAL_IS_CONE_EMIT = 0x408
GOAL_SPOT_MODEL_EFF = 0x40C
EFFSHPINST_SCALE = 0x14
_BOOT_BIT = {"blue": 0x08, "red": 0x10, "yellow": 0x20}  # hasBootContainer (y)
CONE_DEFAULT_SCALE = 0.1   # echelle pleine du cone observee sur tous les oignons
CONE_MAX_TRIES = 5         # corrections max par oignon et par journee
CONE_START_DELAY = 2.0     # #46 : secondes de jeu libre avant de toucher aux cones
MOVIE_IS_ACTIVE = 0x124    # MoviePlayer.mIsActive (bool)


def is_movie_playing(game: Game) -> bool:
    """#46 : vrai si une cinematique (MoviePlayer) est en cours."""
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
    """#34 : avec "Onion Discovery" sautee, force le rayon de tous les oignons
    presents des le debut de la journee.

    Un cone a 0 recoit l'echelle d'un oignon normal (sinon 0.1), ecrite
    directement dans son modele (pas de startConeEmit : il forcerait l'IA d'un
    oignon non decouvert en GOAL_Wait). Le jeu pouvant re-reduire le cone juste
    apres le chargement, on reverifie a chaque tick, au plus CONE_MAX_TRIES fois.
    """
    slot_data = getattr(ctx, "slot_data", None) or {}
    if "Onion Discovery" not in slot_data.get("skip_events", []):
        return
    # #46 : pas pendant la cinematique de debut de journee (atterrissage des
    # oignons, qui ouvre elle-meme les cones) ni sous un menu ; puis on attend
    # CONE_START_DELAY secondes de jeu libre, sinon le rayon apparaissait avant
    # la fin de la cinematique.
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

    # Echelle de reference : celle d'un oignon dont le cone est normal.
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
            continue  # oignon absent de cette zone
        try:
            if dme.read_byte(goal + GOAL_IS_CONE_EMIT) or dme.read_byte(goal + GOAL_IS_CLOSING):
                continue  # animation du jeu en cours
            eff = struct.unpack(">I", dme.read_bytes(goal + GOAL_SPOT_MODEL_EFF, 4))[0]
            if not (_RAM_MIN <= eff < _RAM_MAX):
                continue
            if f32(eff + EFFSHPINST_SCALE) > 0.0:
                continue  # visible pour l'instant : on reverifiera
            tries = ctx._cone_tries.get(color, 0)
            if tries >= CONE_MAX_TRIES:
                ctx._cone_ok.add(color)
                if ctx.debug_pbonus:
                    logger.info(f"[DEBUG] Cone de l'oignon {color} : {CONE_MAX_TRIES} essais, abandon.")
                continue
            ctx._cone_tries[color] = tries + 1
            if f32(goal + GOAL_CONE_FULL_SCALE) <= 0.0:
                dme.write_bytes(goal + GOAL_CONE_FULL_SCALE, full)
            dme.write_bytes(eff + EFFSHPINST_SCALE, full)
            if ctx.debug_pbonus:
                logger.info(f"[DEBUG] Cone de l'oignon {color} relance (echelle {ref:.2f}).")
        except Exception as e:
            if ctx.debug_pbonus:
                logger.info(f"[DEBUG] Cone de l'oignon {color} : erreur {e!r}")


async def handle_qol_min_leaf(ctx: P1Context, game: Game) -> None:
    """QOL 'Always Keep One Leaf Pikmin' : garde >=1 Pikmin Leaf, UNIQUEMENT pour
    les couleurs reellement possedees (hasContainer). Forcer une couleur non
    possedee creait des Pikmin fantomes sans onion associe -> la sequence de fin
    de journee (cinematique d'envol par onion + resultats) plantait sur un
    pointeur nul. Skip la cinematique de nouvelle pousse en debut de journee.
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
            continue  # couleur non possedee -> pas de Pikmin fantome
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
    """QOL Disable Pikmin Trip en mode 'item' : quand l'item 'Trip Immunity' est
    recu, ecrit 2.0f a la place de la constante 0.9999f du test de trip. getRand
    renvoie [0,1[ -> la condition n'est jamais vraie -> plus de trip.

    On ecrit une DONNEE (pas du code) : le JIT de Dolphin la relit a chaque
    execution. Une reecriture de code a chaud (bne->b), elle, restait sans effet
    car Dolphin ne recompile pas un bloc deja JIT-e. On re-verifie/reapplique
    chaque tick (bon marche) pour survivre a un rechargement de la .sdata2."""
    slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
    if int(slot_data.get("disable_pikmin_trip", 1)) != 2:  # option_item
        return
    if not any(it.item == TRIP_IMMUNITY_ITEM_ID for it in ctx.items_received):
        return

    addr = SYM_TRIP_RAND_CONST.get(game)
    if addr is None:
        return  # version sans adresse connue (NTSC) : non applique
    want = struct.pack(">f", TRIP_DISABLED_FLOAT)
    try:
        if dme.read_bytes(addr, 4) != want:
            dme.write_bytes(addr, want)
            if not getattr(ctx, "_trip_ram_patched", False):
                ctx._trip_ram_patched = True
                logger.info(f"[Pikmin] Trip Immunity applique (constante @ 0x{addr:08X}).")
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

    # Adresse resolue dynamiquement a chaque tick : elle depend de l'allocation
    # courante de la fenetre de texte. PAL et NTSC-U.
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

    # Quelle piece est affichee ? On lit gameflow.mShipTextPartID (s16), qui est
    # un symbole STATIQUE present en PAL comme en NTSC. L'ancienne methode
    # cherchait le nom de la piece dans le texte lui-meme : elle dependait de la
    # langue detectee, echouait des qu'une traduction etait absente ou mal
    # orthographiee, et cessait de fonctionner une fois notre propre texte ecrit
    # (le nom d'origine ayant disparu du buffer).
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
        # Meme piece toujours affichee : on reecrit simplement le meme texte.
        # Le mode 3 affiche un texte combine unique (objet + radar), construit
        # par build_hint_bytes(). Il existait une bascule alternant toutes les
        # quelques secondes entre les deux infos, mais elle n'a jamais fonctionne
        # (constante d'intervalle jamais definie) et le texte combine est plus
        # lisible : elle est supprimee.
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
    """#38 : cherche le bloc du nom de slot ecrit par le patcher (P1Rom) dans la
    RAM du jeu (.text du DOL) et renvoie le nom, ou "" (ancienne ISO)."""
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


def _run_in_daemon_thread(func, *args) -> "asyncio.Future":
    """Execute func(*args) in a throwaway daemon thread and return an awaitable.

    Bug fix (#2 - crash/freeze on client close): loop.run_in_executor(None, ...)
    submits work to asyncio's default ThreadPoolExecutor. If a dolphin_memory_engine
    call (hook()/read_bytes()) ever blocks (Dolphin unresponsive, OS hiccup, etc.),
    the worker thread stays stuck running it. concurrent.futures registers an atexit
    hook that joins EVERY thread it has ever spawned, even ones still blocked inside a
    call — the asyncio.wait_for() timeout around the call only stops *waiting* for the
    result, it does not kill the underlying thread. So on process exit (closing the
    client window), Python can hang forever joining that stuck thread, with no error
    message: exactly the reported freeze/crash.
    A plain daemon thread is not tracked by concurrent.futures' shutdown machinery, so
    the interpreter kills it instead of joining it, letting the client actually close.
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

        # #2 : ne pas enchainer un tick complet (lectures DME, handlers) quand
        # la fermeture vient d'etre demandee.
        if ctx.exit_event.is_set():
            break

        ctx.watcher_event.clear()

        if ctx.needs_location_scout:
            # On ne scoute QUE les locations reellement existantes pour ce joueur,
            # fournies par le serveur (missing | checked). Scouter ALL_LOCATIONS
            # (la liste complete codee en dur, dont les 300 locations Pikmin
            # possibles) faisait planter le serveur avec "No location 71500 for
            # player" des que les locations Pikmin etaient activees avec un
            # intervalle : seule une fraction est creee, les autres n'existent pas.
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
            # Si l'ensemble est encore vide (Connected pas totalement traite),
            # on laisse needs_location_scout a True : reessai au prochain tick.

        if ctx.scout_sent and not ctx.scout_received:
            elapsed = time.monotonic() - ctx.scout_sent_time
            if elapsed >= SCOUT_RETRY_INTERVAL:
                ctx.scout_sent_time = time.monotonic()
                server_locs = list(set(ctx.checked_locations) | set(ctx.missing_locations))
                # #41 : message de debug, visible uniquement avec /debughint
                # (les LocationScouts alimentent les hints de pieces).
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
                ctx.dolphin_status_text = "Disconnected - Hook Failed"
                continue

            # Build expected patched Game ID from slot_data
            slot_data = getattr(ctx, "slot_data", {}) or {}
            suffix = slot_data.get("game_id_suffix", "")

            # Une fois patchee, l'ISO ne porte plus GPIP01/GPIE01 : c'est le
            # prefixe du Game ID qui indique la version d'origine, et donc quelles
            # adresses memoire utiliser. P1P = PAL, P1E = NTSC-U.
            base_version = BASE_ID_BY_PATCHED_PREFIX.get(game[:3])

            if base_version is None:
                ctx.dolphin_status_text = "Connected - Wrong Game (patch your ISO first)"
                continue

            # #38 : ISO patchee detectee -> nom du slot + connexion en attente.
            # Relu si une autre ISO patchee est lancee (Game ID different).
            if game != ctx._detected_game_id:
                ctx._detected_game_id = game
                ctx.iso_slot_name = read_iso_slot_name()
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

        # Deux niveaux de verrou selon ce que lit/ecrit chaque handler :
        #   in_level    = Olimar dans un niveau (NewPikiGame)
        #   save_active = niveau OU carte du monde (choix de niveau)
        # A l'ecran titre et au menu de sauvegarde, les deux sont faux.
        in_level = is_in_level(game_version)
        save_active = is_save_active(game_version)

        # #4 Custom Save : chargements / sauvegardes du jeu.
        try:
            track_game_save(ctx, game_version)
        except Exception:
            logger.exception("[Pikmin] Erreur dans track_game_save — la boucle continue.")

        # Message de synchronisation base sur save_active : passer par la carte
        # du monde entre deux niveaux ne doit pas afficher "en pause".
        if save_active != ctx._save_was_loaded:
            lang = getattr(ctx, "detected_language", "en")
            if save_active:
                msg = SYNC_ACTIVE_MSG.get(lang, SYNC_ACTIVE_MSG["en"])
                logger.info(f"[Pikmin] {msg}")
                # Repartir proprement a la reprise : on rescanne les locations et
                # on laisse handle_pikmin_items re-appliquer les bonus recus.
                ctx.needs_location_scout = True
            else:
                msg = SYNC_PAUSED_MSG.get(lang, SYNC_PAUSED_MSG["en"])
                logger.info(f"[Pikmin] {msg}")
            ctx._save_was_loaded = save_active

        # Reinitialise l'etat DeathLink au debut de chaque journee : front montant
        # de "dans un niveau" (entree dans NewPikiGame). Rearme le verrou de
        # securite et repart le comptage. Independant du day cycle (qui peut figer
        # DAY_NUMBER), car il se base sur l'entree effective dans un niveau.
        if in_level and not ctx._in_level_prev:
            # IMPORTANT : initialiser _orima_was_dead avec la VRAIE valeur
            # courante, pas False. Au tout debut de la journee, orimaDead peut
            # encore valoir True (residuel de la mort de la veille, avant que le
            # jeu ne le remette a zero). Forcer False creait un faux front montant
            # True->... et renvoyait un DeathLink au debut de la journee suivante.
            ctx._orima_was_dead = read_orima_dead(game_version)
            ctx._dead_pikis_last = None
            ctx._dead_pikis_sent = 0
            ctx._bond_dead_last = None
            ctx._olimar_bond_last = None
            ctx._cone_ok = set()
            ctx._cone_tries = {}
            ctx._cone_free_since = None
            ctx._suppress_orima_send = False
            ctx._deathlink_locked_this_day = False
            ctx._pending_self_kill = False
            # Nouvelle journee : on leve le verrou pose par un End Day Trap et on
            # arme un court delai de grace avant de reappliquer des traps.
            ctx._traps_suspended_until_next_day = False
            ctx._trap_grace_ticks = 0
            ctx._trap_free_since = None  # #48 : delai commun avec les cones
        ctx._in_level_prev = in_level
        ctx._save_was_loaded_prev_death = save_active

        # Handlers qui LISENT de la memoire propre au niveau (collecte de pieces,
        # compteurs de l'escouade, DeathLink) : uniquement dans un niveau.
        in_level_handlers = (handle_parts, handle_pikmin_locations, handle_pikmin_bond, handle_olimar_bond,
                             handle_onion_cone,
                             handle_population_graph,
                             handle_death_link, handle_traps)
        # Handlers actifs aussi sur la carte du monde : reception d'objets
        # (persistee via STAGE) et deblocage des zones (visible sur la carte).
        save_active_handlers = (handle_pikmin_items, handle_areas,
                                handle_qol_skip_cutscenes,
                                handle_qol_min_leaf)
        # Handlers cosmetiques/mecaniques : tournent toujours (gardes internes).
        always_handlers = (handle_qol_first_day, handle_qol_trip_item, handle_trip_trap_timer,
                           handle_day_cycle, handle_ship_part_hints)

        # #32 (reouvert) : apres le goal, GameExit fait un softReset puis passe en
        # SECTION_MovSample (generique h4m). Le tas est alors reutilise par le
        # decodeur video / la FIFO GX, mais les pointeurs statiques (playerState,
        # tutorialWindow...) gardent leur ancienne valeur. Les handlers "always"
        # (Normal First Day, hints de pieces...) ecrivaient via ces pointeurs
        # perimes -> "GFX FIFO : Opcode inconnu". On ne touche donc plus a la RAM
        # hors du mode histoire (menus de sauvegarde, intro, carte, niveau).
        story_active = _oneplayer_subsection(game_version) in _STORY_SUBSECTIONS
        # #32 : pendant la sequence de fin (decollage -> espace), le jeu reinitialise
        # ses tas pour les cinematiques : aucune ecriture, seul le goal est envoye.
        ending = story_active and is_final_ending(game_version)
        if ending and not ctx.finished_game:
            await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            ctx.finished_game = True
        handlers = list(always_handlers) if story_active and not ending else []
        if save_active and not ending:
            handlers = list(save_active_handlers) + handlers
        # #32 : les handlers "en niveau" LISENT/ECRIVENT des objets de niveau
        # volatils (pelletMgr et radar via handle_parts -> despawn, escouade,
        # etc.). Pendant une cinematique en niveau, mIsPauseAllowed passe a FALSE
        # et ces objets sont demontes/reutilises par le rendu : continuer a les
        # toucher corrompait le flux GPU (Dolphin : "GFX FIFO opcode inconnu 0xf6"
        # apres le goal, pendant la sequence de fin). On ne les lance donc que
        # quand le gameplay est reellement interactif.
        if in_level and is_day_active(game_version):
            handlers = list(in_level_handlers) + handlers

        # Chaque handler est isole : une exception dans l'un d'eux ne doit pas
        # tuer la boucle entiere. Sans ca, une seule erreur (par exemple dans les
        # hints) arretait definitivement la detection des Pikmin, des locations,
        # du cycle de jour et des zones, sans que rien ne le signale en jeu.
        for handler in handlers:
            if ctx.exit_event.is_set():
                break  # #2 : fermeture demandee en cours de tick
            try:
                await handler(ctx, game_version)
            except Exception:
                logger.exception(f"[Pikmin] Erreur dans {handler.__name__} "
                                 f"— la boucle continue.")
        # TODO if "DeathLink" in ctx.tags: handle that

        # Detection de langue : lecture de gsys->mLanguageID a chaque tick.
        # Si la lecture echoue, on garde silencieusement la valeur precedente.
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
        logger.warning(f"[Pikmin] Table de traduction : {problem}")

    parser = get_base_parser()
    parser.add_argument("appik1_file", default="", type=str, nargs="?",
                        help="Path to a .appik1 patch file")
    parsed = parser.parse_args()

    # Resolve patch path from args or CLI argument
    patch_path = appik1_path or parsed.appik1_file

    # Le patch est fait ici, de maniere synchrone, AVANT toute boucle asyncio et
    # avant l'ouverture de la GUI. L'ancienne version le lancait dans un thread
    # executor : le selecteur de fichier et la messagebox partaient alors d'un
    # thread secondaire sans fenetre parente, ce qui produisait une fenetre
    # parasite qui plantait.
    if patch_path and os.path.isfile(patch_path):
        _handle_patch(patch_path)

    async def main() -> None:
        ctx = P1Context(parsed.connect, parsed.password)
        # #38 : la connexion (adresse passee en argument / via le .appik1) est
        # differee jusqu'a la detection de Pikmin dans Dolphin.
        if parsed.connect:
            ctx._pending_connect = parsed.connect
        else:
            logger.info("Please connect to an Archipelago server.")

        if tracker_loaded:
            ctx.run_generator()  # #37 : prepare Universal Tracker
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()

        loop_task = asyncio.create_task(dolphin_loop(ctx), name="game loop")

        # #2 : la fenetre fermee doit TOUJOURS mener a la sortie, meme si
        # kvui.on_stop (qui leve exit_event) n'est jamais appele.
        exit_wait = asyncio.create_task(ctx.exit_event.wait(), name="exit wait")
        waiters = {exit_wait}
        if ctx.ui_task:
            waiters.add(ctx.ui_task)
        await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
        if not ctx.exit_event.is_set():
            logger.info("[Pikmin] UI closed without exit event — forcing client exit.")
            ctx.exit_event.set()
        exit_wait.cancel()
        # #2 : chaque etape de fermeture est bornee dans le temps ; aucune ne
        # doit pouvoir bloquer indefiniment la sortie du client.
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
        # #2 : la session AP est fermee et la sauvegarde locale (persistent
        # storage) est ecrite de maniere synchrone a chaque changement. Sortie
        # immediate : on ne laisse pas la finalisation de l'interpreteur (join
        # des threads d'executor, fermeture Kivy/SDL, threads DME) bloquer la
        # fermeture de la fenetre.
        try:
            faulthandler.cancel_dump_traceback_later()
        except Exception:
            pass
        logging.shutdown()
        os._exit(0)


def _ask_target_version() -> Optional[bytes]:
    """Fenetre a deux boutons : quelle version de Pikmin patcher ?

    Renvoie le Game ID choisi, ou None si l'utilisateur ferme la fenetre.
    Appelee depuis le thread principal, avant le demarrage de la GUI.
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
    # centre la fenetre
    w, h = root.winfo_width(), root.winfo_height()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"+{x}+{y}")
    root.attributes("-topmost", True)
    root.mainloop()

    return choice.get("v")


def _handle_patch(appik1_path: str) -> None:
    """Patch a copy of the user's Pikmin 1 PAL ISO when a .appik1 file is opened.

    Le chemin de l'ISO passe par les settings AP (`pikmin_options.iso_file`).
    S'il est absent de host.yaml ou invalide, AP ouvre lui-meme un selecteur de
    fichier natif et enregistre le choix de l'utilisateur dans host.yaml.
    Appele de maniere synchrone depuis le thread principal, avant la GUI.
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
        # L'utilisateur a annule le selecteur, ou le fichier choisi est invalide.
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

    # Le chemin retenu est persiste dans host.yaml (utile au premier lancement,
    # quand il vient d'etre choisi via le selecteur de fichier).
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
                suffix = str(data.get("GameIdSuffix", ""))  # vide = ancien .appik1
                slot_name = str(data.get("Name", ""))
                opts = data.get("Options", {})
                # Disable Pikmin Trip : 0=off, 1=patch (DOL), 2=item (runtime).
                # On ne grave le patch DOL QUE pour le mode "patch".
                trip_mode = int(opts.get("disable_pikmin_trip", 1))
                disable_trip = (trip_mode == 1)
                # Skips fusionnes dans l'OptionSet skip_events (liste JSON).
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
            # Succes non affiche (demande utilisateur) ; seul l'echec est signale.
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
        # #35 : ISO attendues + SHA-1 du fichier fourni, pour aider le joueur.
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