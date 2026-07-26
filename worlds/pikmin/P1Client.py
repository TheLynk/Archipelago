import asyncio
import json
import os
import struct
import time
from typing import TYPE_CHECKING, Optional

import dolphin_memory_engine as dme

import Utils
from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus
from .P1UI import P1UI
from .P1Data import *
from .P1Symbols import (
    SYM_GAMEFLOW,
    SYM_PIKMIN_ADDRESSES,
    SYM_ONION_DYN_ADDRS,
    SYM_ONION_STAGE_ADDRS,
    SYM_ITEM_MGR_PTR,
    SYM_GSYS_PTR,
    STDSYSTEM_LANGUAGE_OFFSET,
    LANGUAGE_IDS,
    UFO_PART_ORDER,
    SYM_TUTORIAL_WINDOW_PTR,
    TUTORIAL_TEXT_CHAIN,
    TUT_PART_TEXT_RANGES,
    SECTION_ONE_PLAYER,
    ONEPLAYER_NEW_PIKI_GAME,
    ONEPLAYER_MAP_SELECT,
    ONEPLAYER_CARD_SELECT,
    ONION_CHAIN,
    OBJTYPE_GOAL,
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

# containerPikis__8GameStat -- total de Pikmin par couleur dans l'oignon.
ONION_DYN_ADDRS = SYM_ONION_DYN_ADDRS

# Sentinelle de debut de journee: gameflow+0x2EC (0 au menu, non-nul en jeu).
ONION_DYN_SENTINEL = _gf("SENTINEL")

# pikiInfMgr.mPikiCounts[couleur][stade], u32 chacun.
# Le jeu recalcule seul le total affiche = Leaf + Bud + Flower.
ONION_STAGE_ADDRS_CLIENT = SYM_ONION_STAGE_ADDRS


class P1CommandProcessor(ClientCommandProcessor):
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

        log("========== END OF DEBUG DUMP ==========")
        return True


class P1Context(CommonContext):
    command_processor = P1CommandProcessor
    game: str = "Pikmin"
    items_handling: int = 0b111

    def __init__(self, server_address: Optional[str], password: Optional[str]) -> None:
        super().__init__(server_address, password)
        self.dolphin_status_text = "Disconnected"

        # Track Pikmin counts for location checking
        self.pikmin_counts = {"red": 0, "yellow": 0, "blue": 0}
        self.pikmin_location_ids = {}
        self.last_red_count = 0
        self.last_yellow_count = 0
        self.last_blue_count = 0

        # Track how many Pikmin bonus items have already been applied
        self.pikmin_items_applied: dict[int, int] = {}
        # Day start detection for safety check
        self.last_hour: int = -1
        # Debug mode toggles (via /debughint, /debugdays, /debugpbonus)
        self.debug_mode: bool = False  # kept for legacy internal checks
        self.debug_hint: bool = False
        self.debug_days: bool = False
        self.debug_pbonus: bool = False
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
        return P1UI

    async def server_auth(self, password_requested: bool = False) -> None:
        # Pattern standard des clients Archipelago : on ne delegue au parent que
        # pour la saisie du mot de passe, sinon il n'y a rien a faire.
        if password_requested and not self.password:
            await super().server_auth(password_requested)
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
            self.pikmin_dyn_pending = {"red": 0, "yellow": 0, "blue": 0}
            self.load_applied()
            self.needs_location_scout = True
            # Register for hints notifications
            self.stored_data_notification_keys.add(f"_read_hints_{self.team}_{self.slot}")
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
    in_game = (not ctx._onion_dyn_was_zero) and (current_day != 0)

    def add_pikmin(color: str, stage: str, amount: int) -> bool:
        """Applique un bonus. Renvoie True seulement si l'ecriture a durablement
        abouti ; False si on doit reessayer plus tard (item non perdu).

        En jeu, l'oignon vivant (DYN) est la source de verite : le jeu recalcule
        STAGE a partir de lui. Si l'oignon de cette couleur n'est pas encore
        resolu (pas encore deploye dans le niveau), on NE marque PAS l'item
        applique et on n'ecrit rien — sinon l'ecriture STAGE serait ecrasee par
        le jeu et l'item serait perdu. C'etait la cause des Pikmin recus par
        moments non appliques.
        """
        if in_game and stage in DYN_OFFSETS:
            base = getattr(ctx, DYN_BASE_CACHE.get(color, ""), None)
            if not base:
                # Oignon pas encore charge : on retente la resolution.
                base = find_onion_containers(game).get(color)
                if base:
                    setattr(ctx, DYN_BASE_CACHE[color], base)
            if not base:
                # Impossible d'appliquer durablement maintenant -> on differe.
                if ctx.debug_pbonus:
                    logger.info(
                        f"[DEBUG] {color}/{stage} +{amount} deferred: onion not resolved"
                    )
                return False

            # STAGE persistant (survit aux transitions de journee).
            s_addr = stage_addrs[color][stage]
            old_s = read_u32(s_addr)
            write_u32(s_addr, old_s + amount)
            # DYN : oignon vivant, visible immediatement.
            d_addr = base + DYN_OFFSETS[stage]
            old_d = read_u32(d_addr)
            write_u32(d_addr, old_d + amount)
            if ctx.debug_pbonus:
                logger.info(
                    f"[DEBUG] STAGE 0x{s_addr:08X} {color}/{stage} : {old_s} -> {old_s + amount} (+{amount})"
                )
                logger.info(
                    f"[DEBUG] DYN   0x{d_addr:08X} {color}/{stage} : {old_d} -> {old_d + amount} (+{amount})"
                )
            return True

        # Hors journee (oignon non vivant) : on persiste dans STAGE, lu au
        # prochain chargement de journee.
        s_addr = stage_addrs[color][stage]
        old_s = read_u32(s_addr)
        write_u32(s_addr, old_s + amount)
        if ctx.debug_pbonus:
            logger.info(
                f"[DEBUG] STAGE 0x{s_addr:08X} {color}/{stage} : {old_s} -> {old_s + amount} (+{amount}) [not in level]"
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


async def handle_parts(ctx: P1Context, game: Game):
    for name, data in ALL_PARTS.items():
        # check locations if something got collected
        read = dme.read_byte(data.memory_address[game])

        # freshly collected
        if read == data.collected_byte and data.ap_id not in ctx.checked_locations:
            ctx.locations_checked.add(data.ap_id)
            await ctx.check_locations([data.ap_id])


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

    dme.write_byte(COUNT_TOTAL_PARTS[game], ship_parts_count)
    dme.write_byte(COUNT_REQUIRED_PARTS[game], total_required)
    dme.write_byte(UNLOCKED_AREAS[game], areas)


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


async def dolphin_loop(ctx: P1Context):
    game_version = None

    while not ctx.exit_event.is_set():
        try:
            await asyncio.wait_for(ctx.watcher_event.wait(), 1.0)
        except asyncio.TimeoutError:
            pass

        ctx.watcher_event.clear()

        if ctx.needs_location_scout:
            ctx.needs_location_scout = False
            ctx.scout_sent = True
            ctx.scout_sent_time = time.monotonic()
            ctx.scout_received = False

            all_locations = list(ALL_LOCATIONS.values())

            slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
            hint_mode_val = slot_data.get("ship_part_hint_mode", 0)
            if hint_mode_val == 2 or hint_mode_val == 3:
                all_server_locs = set(ctx.checked_locations) | set(ctx.missing_locations)
                all_locations = list(all_server_locs)
                pass

            await ctx.send_msgs([{
                "cmd": "LocationScouts",
                "locations": all_locations,
                "create_as_hint": 0,
            }])

        if ctx.scout_sent and not ctx.scout_received:
            elapsed = time.monotonic() - ctx.scout_sent_time
            if elapsed >= SCOUT_RETRY_INTERVAL:
                ctx.scout_sent_time = time.monotonic()
                logger.info(f"[DEBUG] Retrying LocationScouts (no response after {elapsed:.0f}s, "
                            f"scouted={len(ctx.scouted_locations)})")
                await ctx.send_msgs([{
                    "cmd": "LocationScouts",
                    "locations": list(ALL_LOCATIONS.values()),
                    "create_as_hint": 0,
                }])

        try:
            loop = asyncio.get_event_loop()

            # Run blocking DME calls in an executor with a timeout so that
            # closing Dolphin while the client is running does not freeze the process.
            def _dme_tick():
                if not dme.is_hooked():
                    dme.hook()
                if not dme.is_hooked():
                    return None
                return dme.read_bytes(0x80000000, 6)

            try:
                game = await asyncio.wait_for(
                    loop.run_in_executor(None, _dme_tick),
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

        # Handlers qui LISENT de la memoire propre au niveau (collecte de pieces,
        # compteurs de l'escouade) : uniquement dans un niveau.
        in_level_handlers = (handle_parts, handle_pikmin_locations)
        # Handlers actifs aussi sur la carte du monde : reception d'objets
        # (persistee via STAGE) et deblocage des zones (visible sur la carte).
        save_active_handlers = (handle_pikmin_items, handle_areas)
        # Handlers cosmetiques/mecaniques : tournent toujours (gardes internes).
        always_handlers = (handle_day_cycle, handle_ship_part_hints)

        handlers = list(always_handlers)
        if save_active:
            handlers = list(save_active_handlers) + handlers
        if in_level:
            handlers = list(in_level_handlers) + handlers

        # Chaque handler est isole : une exception dans l'un d'eux ne doit pas
        # tuer la boucle entiere. Sans ca, une seule erreur (par exemple dans les
        # hints) arretait definitivement la detection des Pikmin, des locations,
        # du cycle de jour et des zones, sans que rien ne le signale en jeu.
        for handler in handlers:
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
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")

        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()

        loop_task = asyncio.create_task(dolphin_loop(ctx), name="game loop")

        await loop_task
        await ctx.exit_event.wait()
        await ctx.shutdown()

    import colorama
    colorama.init()
    asyncio.run(main())
    colorama.deinit()


def _ask_target_version() -> Optional[bytes]:
    """Fenetre a deux boutons : quelle version de Pikmin patcher ?

    Renvoie le Game ID choisi, ou None si l'utilisateur ferme la fenetre.
    Appelee depuis le thread principal, avant le demarrage de la GUI.
    """
    from .P1Rom import PAL_GAME_ID, NTSC_GAME_ID

    try:
        import tkinter as tk
    except Exception as e:
        logger.warning(f"[Pikmin] tkinter indisponible ({e}) — PAL par defaut.")
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
    from .P1Rom import verify_iso, patch_iso, InvalidISOError
    from . import get_base_rom_path
    from settings import get_settings
    import shutil

    from .P1Rom import NTSC_GAME_ID, VERSION_LABELS

    target = _ask_target_version()
    if target is None:
        logger.info("[Pikmin] Patch annulé par l'utilisateur.")
        return
    logger.info(f"[Pikmin] Version choisie : {VERSION_LABELS.get(target, target)}")

    setting_name = "iso_file_ntsc" if target == NTSC_GAME_ID else "iso_file"

    try:
        iso_path = get_base_rom_path(target)
    except Exception as e:
        # L'utilisateur a annule le selecteur, ou le fichier choisi est invalide.
        msg = (
            f"Aucune ISO Pikmin 1 {VERSION_LABELS.get(target, '')} valide n'a ete fournie.\n\n"
            f"Detail : {e}\n\n"
            "Vous pouvez aussi renseigner le chemin manuellement dans host.yaml :\n"
            "  pikmin_options:\n"
            f"    {setting_name}: C:/chemin/vers/Pikmin1.iso"
        )
        logger.error(f"[Pikmin] {msg}")
        Utils.messagebox("Cannot Patch Pikmin 1", msg, error=True)
        return

    if not iso_path or not os.path.isfile(iso_path):
        msg = (
            "Aucune ISO Pikmin 1 valide trouvee.\n\n"
            "Renseignez le chemin de l'ISO dans host.yaml :\n"
            "  pikmin_options:\n"
            f"    {setting_name}: C:/chemin/vers/Pikmin1.iso"
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

    # Read seed from .appik1
    seed = ""
    try:
        import zipfile, json
        with zipfile.ZipFile(appik1_path, "r") as zf:
            with zf.open("patch.appik1") as f:
                data = json.load(f)
                seed = str(data.get("Seed", ""))
    except Exception as e:
        logger.warning(f"[Pikmin] Could not read seed from .appik1: {e}")

    # Verify and patch the copy
    try:
        verify_iso(output_iso)
        patch_iso(output_iso, seed=seed)
        logger.info(f"[Pikmin] ISO patched successfully: {output_iso}")
        Utils.messagebox(
            "Pikmin 1 Patched",
            f"Patched ISO created successfully!\n{output_iso}"
        )
    except InvalidISOError as e:
        logger.error(f"[Pikmin] ISO verification failed: {e}")
        try:
            os.remove(output_iso)
        except Exception:
            pass
        Utils.messagebox("Cannot Patch Pikmin 1", str(e), error=True)
    except Exception as e:
        logger.error(f"[Pikmin] Unexpected error during patching: {e}")
        try:
            os.remove(output_iso)
        except Exception:
            pass
        Utils.messagebox("Cannot Patch Pikmin 1", f"Unexpected error:\n{e}", error=True)


if __name__ == "__main__":
    run_client()