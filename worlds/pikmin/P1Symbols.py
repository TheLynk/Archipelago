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
    },
    b'GPIE01': {
        "UNLOCKED_AREAS": 0x8039D983,
        "SENTINEL": 0x8039DAA4,
        "TIME_HOURS": 0x8039DAB0,
        "DAY_NUMBER": 0x8039DAB7,
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
