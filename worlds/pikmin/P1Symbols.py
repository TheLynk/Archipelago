"""Adresses GENEREES par gen_symbols.py -- ne pas editer a la main.
Source: decomp projectPiki/pikmin (GPIP01_00, GPIE01_01).
Regenerer: python gen_symbols.py <decomp>/config worlds/pikmin/P1Symbols.py
"""

# gameflow (jour, heure, zones debloquees)
SYM_GAMEFLOW = {
    b'GPIP01': {
        "UNLOCKED_AREAS": 0x803A2803,
        "SENTINEL": 0x803A2924,
        "TIME_HOURS": 0x803A2930,
        "DAY_NUMBER": 0x803A2937,
        "SHIP_TEXT_PARTID": 0x803A2818,
        "SHIP_TEXT_TYPE": 0x803A281A,
    },
    b'GPIE01': {
        "UNLOCKED_AREAS": 0x8039D983,
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

# Offsets dans la struct PlayerState (include/PlayerState.h)
PLAYERSTATE_OFFSETS = {
    "mTotalRegisteredParts": 0x170,
    "mTotalParts": 0x174,
    "mCurrParts": 0x17C,
    "mRequiredUfoPartCount": 0x180,
    "mContainerFlag": 0x184,
    "mStagePartsCollected": 0x187,
    "mLivingPikiNum": 0x1A8,
    "mPartsCollectedByDay": 0x18,
}
