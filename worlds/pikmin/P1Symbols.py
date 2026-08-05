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
    # Navi.mGoalItem (_708, include/Navi.h) : GoalItem (oignon) auquel Olimar
    # accede quand le menu de l'oignon est ouvert. Sert a savoir quel oignon le
    # joueur a reellement utilise (et non juste croise), pour n'activer le suivi
    # (hasContainer) que de cette couleur.
    "NAVI_GOALITEM": 0x708,
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

# MessageStatus (include/zen/ogMessage.h) : etat REEL de la fenetre de texte,
# dans ogScrMessageMgr.mState (offset MSGMGR_STATE = 0x4CC). ogScrTutorialMgr.mStatus
# n'est qu'un miroir recalcule chaque frame depuis mState -> il faut ecrire ICI.
# Ecrire STATE_Exiting ferme la fenetre au prochain update (comme la fin d'un texte).
MSG_STATE_EXITING = 4

# EDemoFlags de l'explication "container out/in" (texte TUT_OnyonInOut = 12,
# "l'onion rouge t'a suivi") declenchee par Navi::demoCheck des que !isTutorial
# (donc au 1er atterrissage avec normal_first_day). On la PRE-MARQUE "vue" pour
# annuler le declencheur en amont : fermer la fenetre a posteriori soft-lock
# (la demo/camera associee reste active). Aucun effet de bord (cible nullptr).
DEMOFLAG_ONYON_MENU_INFO = 16  # DEMOFLAG_OnyonMenuInfo

# Indices EDemoFlags (include/Demo.h) des cinematiques de decouverte des onions.
DEMOFLAG_DISCOVER_ONION = {
    "red": 0,     # DEMOFLAG_DiscoverRedOnyon
    "yellow": 1,  # DEMOFLAG_DiscoverYellowOnyon
    "blue": 2,    # DEMOFLAG_DiscoverBlueOnyon
}

# Indices EDemoFlags des cinematiques de premiere extraction d'une couleur de Pikmin.
DEMOFLAG_PLUCK_PIKMIN = {
    "red": 4,     # DEMOFLAG_PluckRedPikmin
    "yellow": 5,  # DEMOFLAG_PluckYellowPikmin
    "blue": 6,    # DEMOFLAG_PluckBluePikmin
}

# EDemoFlags de la 1re rentree d'un pellet dans un onion (texte TUT_Pelette = 6).
DEMOFLAG_COLLECT_FIRST_PELLET = 10  # DEMOFLAG_CollectFirstPellet

# EDemoFlags de la decouverte du Main Engine dans The Impact Site.
DEMOFLAG_APPROACH_ENGINE = 12  # DEMOFLAG_ApproachEngine

# EDemoFlags de la COLLECTE du Main Engine (1re piece). En le marquant "vu", la
# collecte du moteur passe par la branche "piece normale" de PelletGoalState::init
# (dont le film movie(DEMOID_CollectPart) est deja nop-e par le patch DOL) au lieu
# de la branche tutoriel qui joue movie(20). -> plus de cinematique pour le moteur.
DEMOFLAG_COLLECT_ENGINE = 13  # DEMOFLAG_CollectEngine

# EDemoFlags de la cinematique "10 Pikmin poussent la boite" (The Impact Site).
DEMOFLAG_BOX_PUSH = (14, 15)  # StartBoxPush (film) + FinishBoxPush

# EDemoFlags de la cinematique "Pikmin jaune rapporte une bombe" (texte
# TUT_FoundBomb = 16), posee dans ActCrowd (aiCrowd.cpp) via DEMOFLAG_GrabFirstBomb.
DEMOFLAG_GRAB_FIRST_BOMB = 18  # DEMOFLAG_GrabFirstBomb

# EDemoFlags du texte d'explication du nectar (TUT_Mitu = 22).
DEMOFLAG_FIRST_NECTAR = 26  # DEMOFLAG_FirstNectar

# EDemoFlags du texte de 1re explosion de bombe (TUT_BombInfo = 20). Envoye
# directement dans DemoFlags::update(). update() court-circuite via isFlag(),
# donc pre-marquer le flag suffit a annuler le texte.
DEMOFLAG_FIRST_BOMB_EXPLODE = 20  # DEMOFLAG_FirstBombExplode

# EDemoFlags du texte de degats sur Olimar (affiche ID 24 en jeu ; le flag est
# nomme "ORIMA DAMAGED" dans la decomp).
DEMOFLAG_OLIMAR_LOW_HEALTH = 29  # DEMOFLAG_OlimarLowHealth

# EDemoFlags du texte sur le chemin de transport bloque (TUT_Rute = 23 ;
# flag "GURU GURU" = les Pikmin tournent en rond).
DEMOFLAG_CARRY_PATH_BLOCKED = 28  # DEMOFLAG_CarryPathBlocked

# EDemoFlags des textes "vous avez depasse 100 Pikmin" (un par zone, 21..25).
DEMOFLAG_PIKMIN_LIMIT = (21, 22, 23, 24, 25)

# EDemoFlags du texte d'info affiche au 1er midi (TUT_InfoDisplay = 31),
# declenche dans GameCoreSection::update gardé par !isFlag(DEMOFLAG_FirstNoon).
DEMOFLAG_FIRST_NOON = 31  # DEMOFLAG_FirstNoon

# Adresse de la constante flottante 0.9999f du test de trebuchement
# (ActCrowd::exec : `getRand(1.0f) >= 0.9999f`), en .sdata2, par version.
# Mode "item" de Disable Pikmin Trip : a la reception de l'item, le client ecrit
# 2.0f ici. getRand(1.0f) renvoie [0,1[ -> la condition n'est jamais vraie -> plus
# de trip. C'est une DONNEE (pas du code) : le JIT de Dolphin la relit a chaque
# execution, contrairement a une reecriture de code a chaud qui reste sans effet.
# Cette copie de 0.9999 n'est utilisee QUE par le test de trip (les autres tests
# 0.9999 du jeu utilisent d'autres copies .sdata2). PAL verifie a l'ISO ; NTSC
# absent (adresse a deriver d'une ISO NTSC) -> mode item non applique en NTSC.
SYM_TRIP_RAND_CONST = {
    b"GPIP01": 0x803EE264,
}
TRIP_DISABLED_FLOAT = 2.0  # ecrit a la place de 0.9999 pour annuler le trip

# ---------------------------------------------------------------------------
# OptionSet "skip_events" : cle lisible -> indices EDemoFlags a pre-marquer.
# Une cle presente dans l'OptionSet du joueur = cette cinematique / ce texte est
# saute (le client pre-marque les DemoFlags correspondants).
#   - "Onion Discovery" declenche aussi la reparation suivi/affichage d'onion
#     (voir handle_qol_skip_cutscenes).
#   - "Part Collection" implique EN PLUS le patch DOL du film de collecte.
#   - "Ship Upgrade" est un patch DOL uniquement (aucun DemoFlag) -> pas ici.
# ---------------------------------------------------------------------------
SKIP_EVENT_DEMOFLAGS = {
    # --- Cinematiques ---
    "Onion Discovery":       tuple(DEMOFLAG_DISCOVER_ONION.values()),
    "New Pikmin":            tuple(DEMOFLAG_PLUCK_PIKMIN.values()),
    "Main Engine Discovery": (DEMOFLAG_APPROACH_ENGINE,),
    "First Pellet":          (DEMOFLAG_COLLECT_FIRST_PELLET,),
    "Part Collection":       (DEMOFLAG_COLLECT_ENGINE,),  # + patch DOL
    "Box Push":              tuple(DEMOFLAG_BOX_PUSH),
    "First Bomb":            (DEMOFLAG_GRAB_FIRST_BOMB,),
    # --- Textes ---
    "Pikmin Limit":          tuple(DEMOFLAG_PIKMIN_LIMIT),
    "Bomb Explosion":        (DEMOFLAG_FIRST_BOMB_EXPLODE,),
    "Olimar Damage":         (DEMOFLAG_OLIMAR_LOW_HEALTH,),
    "Carry Path":            (DEMOFLAG_CARRY_PATH_BLOCKED,),
    "First Noon":            (DEMOFLAG_FIRST_NOON,),
    "Onion Followed":        (DEMOFLAG_ONYON_MENU_INFO,),
    "Nectar":                (DEMOFLAG_FIRST_NECTAR,),
}
# Toutes les cles valides de l'OptionSet (DemoFlags + "Ship Upgrade" DOL-only).
SKIP_EVENT_ALL_KEYS = tuple(SKIP_EVENT_DEMOFLAGS.keys()) + ("Ship Upgrade",)

# PlayerState.mContainerFlag (offset 0x184) : octet 00 yyy xxx.
#   x (bits 0..2) = hasContainer(couleur) : l'oignon est possede et suit entre zones.
#       bit = 1 << indexCouleur (Blue=0, Red=1, Yellow=2).
#   y (bits 3..5) = hasBootContainer(couleur) : l'oignon est "demarre" (actif).
#       bit = 1 << (indexCouleur + 3).
# Sauter la cinematique de decouverte prive le jeu de ces mises a jour : on les
# reproduit (boot pour activer, container pour le suivi entre journees/zones).
CONTAINER_COLOR_BIT = {"blue": 0x01, "red": 0x02, "yellow": 0x04}  # hasContainer (x)
CONTAINER_BOOT_ALL = 0x38  # tous les bits hasBootContainer (y), bits 3/4/5

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
    # PlayerState.mDemoFlags (_54) est un DemoFlags ; son champ mStoredFlags (_08)
    # est un pointeur vers u8[32] (bitset des cinematiques deja vues, indexe par
    # EDemoFlags). Offset du POINTEUR dans PlayerState : 0x54 + 0x08 = 0x5C.
    # Marquer un bit = la cinematique correspondante ne se joue plus (le jeu voit
    # isFlag()==true). include/Demo.h + include/PlayerState.h.
    "mDemoFlagsStoredPtr": 0x5C,
    # bool PlayerState.mIsTutorialMode (_185, include/PlayerState.h). isTutorial()
    # le renvoie tel quel. TRUE => jour 1 special : intro du crash (DEMOID_OlimarWakeUp),
    # horloge figee et pop-ups de tutoriel. Le forcer a 0 rend le jour 1 classique.
    "mIsTutorialMode": 0x185,
    "mStagePartsCollected": 0x187,
    # u8 PlayerState.mDisplayPikiFlag (_1AC) : bit (1<<couleur) par couleur dont le
    # compteur de Pikmin s'affiche (HUD, carte du monde, resume de fin de journee).
    # Pose par setDisplayPikiCount(). Sauter la decouverte d'onion le laissait a 0
    # pour bleu/jaune -> onions possedes non affiches dans les menus.
    "mDisplayPikiFlag": 0x1AC,
    "mLivingPikiNum": 0x1A8,
    "mPartsCollectedByDay": 0x18,
}
