"""Adresses GENEREES par gen_symbols.py -- ne pas editer a la main.
Source: decomp projectPiki/pikmin (GPIP01_00, GPIE01_01).
Regenerer: python gen_symbols.py <decomp>/config worlds/pikmin/P1Symbols.py
"""

# gameflow (jour, heure, zones debloquees)
SYM_GAMEFLOW = {
    b'GPIP01': {
        "UNLOCKED_AREAS": 0x803A2803,
        "GAME_SECTION": 0x803A2824,
        "DAY_END_TRIGGERED": 0x803A281E,
        "TIME_OF_DAY": 0x803A2928,
        "PAUSE_ALLOWED": 0x803A296C,
        "ONEPLAYER_SECTION": 0x803A282C,
        "SENTINEL": 0x803A2924,
        "TIME_HOURS": 0x803A2930,
        "DAY_NUMBER": 0x803A2937,
        "SHIP_TEXT_PARTID": 0x803A2818,
        "SHIP_TEXT_TYPE": 0x803A281A,
    },
    b'GPIE01': {
        "UNLOCKED_AREAS": 0x8039D983,
        "GAME_SECTION": 0x8039D9A4,
        "DAY_END_TRIGGERED": 0x8039D99E,
        "TIME_OF_DAY": 0x8039DAA8,
        "PAUSE_ALLOWED": 0x8039DAEC,
        "ONEPLAYER_SECTION": 0x8039D9AC,
        "SENTINEL": 0x8039DAA4,
        "TIME_HOURS": 0x8039DAB0,
        "DAY_NUMBER": 0x8039DAB7,
        "SHIP_TEXT_PARTID": 0x8039D998,
        "SHIP_TEXT_TYPE": 0x8039D99A,
    },
}

# formationPikis__8GameStat -- octet faible par couleur
SYM_PIKMIN_ADDRESSES = {
    b'GPIP01': {
        "blue": 0x803D6CF3,
        "red": 0x803D6CF7,
        "yellow": 0x803D6CFB,
    },
    b'GPIE01': {
        "blue": 0x803D1E73,
        "red": 0x803D1E77,
        "yellow": 0x803D1E7B,
    },
}

# containerPikis__8GameStat -- total par couleur
SYM_ONION_DYN_ADDRS = {
    b'GPIP01': {
        "blue": 0x803D6D20,
        "red": 0x803D6D24,
        "yellow": 0x803D6D28,
    },
    b'GPIE01': {
        "blue": 0x803D1EA0,
        "red": 0x803D1EA4,
        "yellow": 0x803D1EA8,
    },
}

# pikiInfMgr.mPikiCounts[couleur][stade] (u32)
SYM_ONION_STAGE_ADDRS = {
    b'GPIP01': {
        "blue": {"leaf": 0x803D6C70, "bud": 0x803D6C74, "flower": 0x803D6C78},
        "red": {"leaf": 0x803D6C7C, "bud": 0x803D6C80, "flower": 0x803D6C84},
        "yellow": {"leaf": 0x803D6C88, "bud": 0x803D6C8C, "flower": 0x803D6C90},
    },
    b'GPIE01': {
        "blue": {"leaf": 0x803D1DF0, "bud": 0x803D1DF4, "flower": 0x803D1DF8},
        "red": {"leaf": 0x803D1DFC, "bud": 0x803D1E00, "flower": 0x803D1E04},
        "yellow": {"leaf": 0x803D1E08, "bud": 0x803D1E0C, "flower": 0x803D1E10},
    },
}

# playerState -- POINTEUR global, a dereferencer avant usage
SYM_PLAYER_STATE_PTR = {
    b'GPIP01': 0x803ECB4C,
    b'GPIE01': 0x803E7C8C,
}

# itemMgr -- POINTEUR global vers ItemMgr
SYM_ITEM_MGR_PTR = {
    b'GPIP01': 0x803ECC8C,
    b'GPIE01': 0x803E7DCC,
}

# DeathLink -- deadPikis (ColCounter: 3 int Blue/Red/Yellow, total = somme).
SYM_DEAD_PIKIS = {
    b'GPIP01': 0x803D6CD8,
    b'GPIE01': 0x803D1E58,
}

# DeathLink -- orimaDead (bool, 1 = Olimar mort). Mis a 1 par NaviDeadState.
SYM_ORIMA_DEAD = {
    b'GPIP01': 0x803ECCE8,
    b'GPIE01': 0x803E7E28,
}

# naviMgr -- POINTEUR global vers NaviMgr (pour atteindre Olimar).
SYM_NAVI_MGR_PTR = {
    b'GPIP01': 0x803ECD00,
    b'GPIE01': 0x803E7E40,
}

# Chaine naviMgr -> Olimar (Navi) et champs de Navi/Creature.
#   naviMgr -> +MONO_OBJECTLIST (Creature**) -> [0] = Navi (Olimar 1 joueur)
#   Navi + CREATURE_HEALTH = mHealth (f32), <= 1.0 => mort
#   Navi + NAVI_STATEMACHINE = mStateMachine
NAVI_CHAIN = {
    "MONO_OBJECTLIST": 0x28,
    "CREATURE_HEALTH": 0x58,
    "NAVI_STATEMACHINE": 0x320,
    "NAVI_PRESSED_TIMER": 0x814,
    "NAVI_CURRSTATE": 0xADC,
    "CREATURE_POSITION": 0x94,
    "CREATURE_STICKLIST": 0x180,
    "NAVI_KONTROLLER": 0x2E4,
    "CONTROLLER_INPUT_PRESSED": 0x28,
    "SM_STATES": 0x4,
    "SM_STATEINDEXES": 0x14,
}
NAVISTATE_DEAD = 29     # enum NaviStateID (include/NaviState.h) -- etat mort
NAVISTATE_PRESSED = 7   # etat 'ecrase' : son exec() verifie la sante et transite vers Dead
NAVISTATE_WALK = 0      # etat marche : son exec() transite vers Stuck si mStickListHead != 0
KBBTN_X = 0x4000        # bouton X = touche de disband par defaut (keyConfig.cpp:39)

# routeMgr -- POINTEUR global vers RouteMgr (graphe de navigation Pikmin).
# Sert au Teleport Trap : on teleporte Olimar sur un waypoint valide (donc
# sur le terrain navigable, jamais dans le vide).
SYM_ROUTE_MGR_PTR = {
    b'GPIP01': 0x803ECC0C,
    b'GPIE01': 0x803E7D4C,
}
# Chaine routeMgr -> waypoints et champs de WayPoint (include/Route.h).
ROUTE_CHAIN = {
    "ROUTEMGR_GROUPLIST": 0x20,
    "GROUP_WAYPOINTS": 0x0,
    "GROUP_NUMPOINTS": 0x4,
    "WAYPOINT_SIZE": 0xC4,
    "WP_POSITION": 0x0,
    "WP_ISOPEN": 0x38,
    "WP_FLAGS": 0x40,
}
WP_FLAG_INWATER = 0x01  # WayPointFlags::InWater (bit 0)

# enum GameSectionID (include/Section.h). Valeur de gameflow.mCurrGameSectionID.
SECTION_ONE_PLAYER = 4  # mode histoire/challenge : une partie est chargee
SECTION_TITLES = 1      # ecran titre

# enum OnePlayerSectionID (include/Section.h). Valeur de mNextOnePlayerSectionID.
ONEPLAYER_NEW_PIKI_GAME = 7  # journee de jeu reelle (Olimar dans un niveau)
ONEPLAYER_CARD_SELECT = 1    # menu de selection de sauvegarde
ONEPLAYER_MAP_SELECT = 6     # carte du monde / selection de zone

# tutorialWindow -- POINTEUR statique vers zen::ogScrTutorialMgr
# (cree dans createTutorialWindow(), src/plugPikiColin/newPikiGame.cpp).
SYM_TUTORIAL_WINDOW_PTR = {
    b'GPIP01': 0x803ECA68,
    b'GPIE01': 0x803E7BA8,
}

# Chaine vers le texte affiche a l'ecran :
#   tutorialWindow -> ogScrTutorialMgr +MESSAGEMGR -> ogScrMessageMgr
#   -> +FORMATTED_STRINGS (mFormattedDisplayStrings[20][0x400])
# Offsets issus de include/zen/ogTutorial.h et include/zen/ogMessage.h.
# La structure n'est pas conditionnee a la version : identique PAL/NTSC.
TUTORIAL_TEXT_CHAIN = {
    "TUTORIALMGR_MESSAGEMGR": 0x0,
    "TUTORIALMGR_STATUS": 0x4,
    "MSGMGR_PAGE_INFOS": 0x1C,
    "MSGMGR_STATE": 0x4CC,
    "MSGMGR_CURR_PAGE": 0x4D0,
    "MSGMGR_FORMATTED": 0x4F2,
    "MSGMGR_RAW": 0x554C,
    "MSGMGR_STRING_STRIDE": 0x400,
    "TEXTINFO_MSG_UNIQUE_ID": 0x4,
}

# Plages de l'enum EnumTutorial (include/zen/ogTutorial.h) correspondant
# aux textes de pieces de vaisseau. Chaque plage couvre les 30 pieces,
# dans l'ordre de UfoPartIndex. Tout ID hors de ces plages est un texte
# de tutoriel ou de scenario, qu'il ne faut PAS remplacer.
TUT_PART_TEXT_RANGES = {
    "discovery": 32,
    "info": 62,
    "collect": 92,
    "power": 122,
}

# enum UfoPartIndex (include/Pellet.h) -> nom de piece dans ALL_PARTS.
# L'index lu dans gameflow.mShipTextPartID indexe directement cette liste.
UFO_PART_ORDER = [
    'Bowsprit',
    'Gluon Drive',
    'Anti-Dioxin Filter',
    'Eternal Fuel Dynamo',
    'Main Engine',
    'Whimsical Radar',
    'Interstellar Radio',
    'Guard Satellite',
    'Chronos Reactor',
    'Radiation Canopy',
    'Geiger Counter',
    'Sagittarius',
    'Libra',
    'Omega Stabilizer',
    '#1 Ionium Jet',
    '#2 Ionium Jet',
    'Shock Absorber',
    'Gravity Jumper',
    "Pilot's Seat",
    'Nova Blaster',
    'Automatic Gear',
    'Zirconium Rotor',
    'Extraordinary Bolt',
    'Repair-type Bolt',
    'Space Float',
    'Massage Machine',
    'Secret Safe',
    'Positron Generator',
    'Analog Computer',
    'UV Lamp',
]
UFO_NOPART = -1  # aucune piece / index invalide

# gsys -- POINTEUR global vers System (System : public StdSystem, include/system.h)
SYM_GSYS_PTR = {
    b'GPIP01': 0x803EC9CC,
    b'GPIE01': 0x803E7B0C,
}

# StdSystem.mLanguageID (include/system.h). Membre PAL uniquement :
# en NTSC-U le champ n'existe pas (jeu anglais seul) et 0x1A0 y porte
# le pointeur de vtable -- ne jamais le lire hors GPIP01.
STDSYSTEM_LANGUAGE_OFFSET = 0x1A0

# enum LanguageID (include/system.h). ATTENTION : cet ordre n'est PAS
# celui de l'OS GameCube (OS_LANG_GERMAN=1 / OS_LANG_FRENCH=2) ; le jeu
# remappe via la table ids[] de GamePrefs::Initialise().
LANGUAGE_IDS = {
    0: "en",
    1: "fr",
    2: "de",
    3: "es",
    4: "it",
}

# Chaine de pointeurs vers les oignons vivants (remplace le scan RAM).
# itemMgr -> +MELTINGPOT -> +ROOTNODE +CHILD -> [ +MCREATURE ] -> GoalItem
# puis on suit +NEXT de noeud en noeud.
ONION_CHAIN = {
    "ITEMMGR_MELTINGPOT": 0x68,
    "MGR_ROOTNODE": 0x28,
    "NODE_NEXT": 0xC,
    "NODE_CHILD": 0x10,
    "NODE_CREATURE": 0x14,
    "CREATURE_OBJTYPE": 0x6C,
    "GOAL_COLOUR": 0x428,
    "GOAL_HELDPIKIS": 0x42C,
}
OBJTYPE_GOAL = 16  # ObjType.h
OBJTYPE_PELLET = 52  # ObjType.h -- tous les pellets (dont pieces de vaisseau)

# pelletMgr -- POINTEUR global vers PelletMgr (MonoObjectMgr des pellets,
# dont les pieces de vaisseau). C'est ICI que sont les pellets, PAS itemMgr.
SYM_PELLET_MGR_PTR = {
    b'GPIP01': 0x803ECBFC,
    b'GPIE01': 0x803E7D3C,
}
# Champs de MonoObjectMgr (include/ObjectMgr.h) + Pellet/PelletConfig
# (include/Pellet.h) pour enumerer et retirer un Pellet de piece de vaisseau.
PELLET_CHAIN = {
    "MONO_OBJECTLIST": 0x28,
    "MONO_MAXELEMENTS": 0x2C,
    "MONO_ENTRYSTATUS": 0x34,
    "PELLET_CONFIG": 0x55C,
    "PELLETCONFIG_MODELID": 0x2C,
    "PELLET_ISALIVE": 0x5B8,
}
ENTRYSTATUS_KILL = -2  # mEntryStatus[i] = -2 -> MonoObjectMgr::update tue l'objet

# radarInfo -- POINTEUR global vers RadarInfo. Le radar dessine une icone
# par noeud de mAlivePartsList ; retirer une piece = delier son noeud
# (comme RadarInfo::detachParts). Noeuds = CoreNode (mNext _0C), mPart _14.
SYM_RADAR_INFO_PTR = {
    b'GPIP01': 0x803ECB08,
    b'GPIE01': 0x803E7C48,
}
RADAR_CHAIN = {
    "ALIVE_CHILD": 0x10,
    "NODE_NEXT": 0xC,
    "NODE_PART": 0x14,
}

# Offsets dans la struct PlayerState (include/PlayerState.h)
PLAYERSTATE_OFFSETS = {
    "mShipEffectPartFlag": 0x11,
    "mTotalRegisteredParts": 0x170,
    "mTotalParts": 0x174,
    "mCurrParts": 0x17C,
    "mRequiredUfoPartCount": 0x180,
    "mContainerFlag": 0x184,
    "mStagePartsCollected": 0x187,
    "mLivingPikiNum": 0x1A8,
    "mPartsCollectedByDay": 0x18,
}
