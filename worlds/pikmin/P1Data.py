from dataclasses import dataclass
from typing import Literal, Dict
from BaseClasses import ItemClassification

Area = Literal["The Impact Site", "The Forest of Hope", "The Forest Navel", "The Distant Spring", "The Final Trial"]
Game = Literal[b"GPIJ01", b"GPIE01", b"GPIP01", b"R9IJ01", b"R9IE01", b"R9IP01", b"R9IK01"]

MemoryAddress = dict[Game, int]  # can have byte strings


@dataclass
class RequiredTypes:
    red: bool
    yellow: bool
    blue: bool


@dataclass
class ShipPartData:
    ap_id: int
    memory_address: MemoryAddress
    collected_byte: int
    required_types: RequiredTypes
    area: Area


def mem(GPIP01: int, GPIE01: int) -> MemoryAddress:
    return {b"GPIP01": GPIP01, b"GPIE01": GPIE01}


ALL_PARTS: dict[str, ShipPartData] = {
    "Bowsprit": ShipPartData(71400, mem(0x8123FFF4, 0x812475DC), 1, RequiredTypes(False, False, False), "The Distant Spring"), # ust1
    "Gluon Drive": ShipPartData(71401, mem(0x812400D4, 0x812476BC), 1, RequiredTypes(False, False, True), "The Distant Spring"), # ust2
    "Anti-Dioxin Filter": ShipPartData(71402, mem(0x812401B4, 0x8124779C), 1, RequiredTypes(False, False, True), "The Forest Navel"), # ust3
    "Eternal Fuel Dynamo": ShipPartData(71403, mem(0x81240294, 0x8124787C), 1, RequiredTypes(False, False, False), "The Forest of Hope"), # ust4
    "Main Engine": ShipPartData(71404, mem(0x81240374, 0x8124795C), 1, RequiredTypes(False, False, False), "The Impact Site"), # ust5
    "Whimsical Radar": ShipPartData(71405, mem(0x81240454, 0x81247A3C), 1, RequiredTypes(False, True, False), "The Forest of Hope"), # uf01
    "Interstellar Radio": ShipPartData(71406, mem(0x81240534, 0x81247B1C), 1, RequiredTypes(False, False, True), "The Distant Spring"), # uf02
    "Guard Satellite": ShipPartData(71407, mem(0x81240614, 0x81247BFC), 1, RequiredTypes(True, True, False), "The Forest Navel"), # uf03
    "Chronos Reactor": ShipPartData(71408, mem(0x812406F4, 0x81247CDC), 1, RequiredTypes(False, True, True), "The Distant Spring"), # uf04
    "Radiation Canopy": ShipPartData(71409, mem(0x812407D4, 0x81247DBC), 1, RequiredTypes(False, True, True), "The Forest of Hope"), # uf05
    "Geiger Counter": ShipPartData(71410, mem(0x812408B4, 0x81247E9C), 1, RequiredTypes(False, True, True), "The Forest of Hope"), # uf06
    "Sagittarius": ShipPartData(71411, mem(0x81240994, 0x81247F7C), 1, RequiredTypes(False, False, True), "The Forest of Hope"), # uf07
    "Libra": ShipPartData(71412, mem(0x81240A74, 0x8124805C), 1, RequiredTypes(True, True, True), "The Forest Navel"), # uf08
    "Omega Stabilizer": ShipPartData(71413, mem(0x81240B54, 0x8124813C), 1, RequiredTypes(False, False, False), "The Forest Navel"), # uf09
    "#1 Ionium Jet": ShipPartData(71414, mem(0x81240C34, 0x8124821C), 1, RequiredTypes(False, False, True), "The Forest Navel"), # uf10
    "#2 Ionium Jet": ShipPartData(71415, mem(0x81240D14, 0x812482FC), 1, RequiredTypes(False, False, True), "The Distant Spring"), # uf11
    "Shock Absorber": ShipPartData(71416, mem(0x81240DF4, 0x812483DC), 2, RequiredTypes(False, False, False), "The Forest of Hope"), # un01
    "Gravity Jumper": ShipPartData(71417, mem(0x81240ED4, 0x812484BC), 2, RequiredTypes(False, False, True), "The Forest Navel"), # un02
    "Pilot's Seat": ShipPartData(71418, mem(0x81240FB4, 0x8124859C), 2, RequiredTypes(False, False, False), "The Distant Spring"), # un03
    "Nova Blaster": ShipPartData(71419, mem(0x81241094, 0x8124867C), 2, RequiredTypes(False, True, False), "The Forest of Hope"), # un04
    "Automatic Gear": ShipPartData(71420, mem(0x81241174, 0x8124875C), 2, RequiredTypes(False, False, False), "The Forest Navel"), # un05
    "Zirconium Rotor": ShipPartData(71421, mem(0x81241254, 0x8124883C), 2, RequiredTypes(False, True, True), "The Distant Spring"), # un06
    "Extraordinary Bolt": ShipPartData(71422, mem(0x81241334, 0x8124891C), 2, RequiredTypes(False, True, False), "The Forest of Hope"), # un07
    "Repair-type Bolt": ShipPartData(71423, mem(0x81241414, 0x812489FC), 2, RequiredTypes(False, False, True), "The Distant Spring"), # un08
    "Space Float": ShipPartData(71424, mem(0x812414F4, 0x81248ADC), 2, RequiredTypes(False, False, False), "The Forest Navel"), # un09
    "Massage Machine": ShipPartData(71425, mem(0x812415D4, 0x81248BBC), 2, RequiredTypes(False, False, True), "The Distant Spring"), # un10
    "Secret Safe": ShipPartData(71426, mem(0x812416B4, 0x81248C9C), 2, RequiredTypes(True, True, True), "The Final Trial"), # un11
    "Positron Generator": ShipPartData(71427, mem(0x81241794, 0x81248D7C), 2, RequiredTypes(False, True, True), "The Impact Site"), # un12
    "Analog Computer": ShipPartData(71428, mem(0x81241874, 0x81248E5C), 2, RequiredTypes(True, False, True), "The Forest Navel"), # un13
    "UV Lamp": ShipPartData(71429, mem(0x81241954, 0x81248F3C), 2, RequiredTypes(False, True, False), "The Distant Spring"), # un14
}


# ====================================================================
# ONION STAGE ADDRESSES - Persistent pikmin counts per stage (PAL, u32 each)
# Total displayed in-game = Leaf + Bud + Flower (recalculated by the game)
# ====================================================================

ONION_STAGE_ADDRS_PAL: dict[str, dict[str, int]] = {
    "red": {
        "leaf":   0x803D6C7C,
        "bud":    0x803D6C80,
        "flower": 0x803D6C84,
    },
    "yellow": {
        "leaf":   0x803D6C88,
        "bud":    0x803D6C8C,
        "flower": 0x803D6C90,
    },
    "blue": {
        "leaf":   0x803D6C70,
        "bud":    0x803D6C74,
        "flower": 0x803D6C78,
    },
}

ONION_STAGE_ADDRS: dict[bytes, dict[str, dict[str, int]]] = {
    b"GPIP01": ONION_STAGE_ADDRS_PAL,
}


# ====================================================================
# FILLER ITEMS - Items that interact with the game
# 18 items : 1 and 5 pikmin × 3 colors × 3 stages (Leaf / Bud / Flower)
# ====================================================================

FILLER_ITEMS: dict[str, int] = {
    # Red
    "1 Red Leaf Pikmin":      71800,
    "5 Red Leaf Pikmin":      71801,
    "1 Red Bud Pikmin":       71802,
    "5 Red Bud Pikmin":       71803,
    "1 Red Flower Pikmin":    71804,
    "5 Red Flower Pikmin":    71805,
    # Yellow
    "1 Yellow Leaf Pikmin":   71806,
    "5 Yellow Leaf Pikmin":   71807,
    "1 Yellow Bud Pikmin":    71808,
    "5 Yellow Bud Pikmin":    71809,
    "1 Yellow Flower Pikmin": 71810,
    "5 Yellow Flower Pikmin": 71811,
    # Blue
    "1 Blue Leaf Pikmin":     71812,
    "5 Blue Leaf Pikmin":     71813,
    "1 Blue Bud Pikmin":      71814,
    "5 Blue Bud Pikmin":      71815,
    "1 Blue Flower Pikmin":   71816,
    "5 Blue Flower Pikmin":   71817,
}

# Map item name -> (color, stage, count) for client-side handling
PIKMIN_BONUS_ITEMS: dict[str, tuple[str, str, int]] = {
    "1 Red Leaf Pikmin":      ("red",    "leaf",   1),
    "5 Red Leaf Pikmin":      ("red",    "leaf",   5),
    "1 Red Bud Pikmin":       ("red",    "bud",    1),
    "5 Red Bud Pikmin":       ("red",    "bud",    5),
    "1 Red Flower Pikmin":    ("red",    "flower", 1),
    "5 Red Flower Pikmin":    ("red",    "flower", 5),
    "1 Yellow Leaf Pikmin":   ("yellow", "leaf",   1),
    "5 Yellow Leaf Pikmin":   ("yellow", "leaf",   5),
    "1 Yellow Bud Pikmin":    ("yellow", "bud",    1),
    "5 Yellow Bud Pikmin":    ("yellow", "bud",    5),
    "1 Yellow Flower Pikmin": ("yellow", "flower", 1),
    "5 Yellow Flower Pikmin": ("yellow", "flower", 5),
    "1 Blue Leaf Pikmin":     ("blue",   "leaf",   1),
    "5 Blue Leaf Pikmin":     ("blue",   "leaf",   5),
    "1 Blue Bud Pikmin":      ("blue",   "bud",    1),
    "5 Blue Bud Pikmin":      ("blue",   "bud",    5),
    "1 Blue Flower Pikmin":   ("blue",   "flower", 1),
    "5 Blue Flower Pikmin":   ("blue",   "flower", 5),
}


# ====================================================================
# TRAP ITEMS
# ====================================================================
# Items de trap (effets negatifs). Appliques en jeu par le client.
# Cle interne -> id AP. Le nom lisible sert d'identifiant unique.

TRAP_ITEMS: dict[str, int] = {
    "Time Trap":      71818,   # avance l'horloge (reduit le temps restant)
    "End Day Trap":   71819,   # force la fin de la journee en cours
    "Damage Trap":    71820,   # blesse Olimar (sante reduite)
    "Teleport Trap":  71821,   # teleporte Olimar a un endroit aleatoire proche
    "Disbanding Trap": 71822,  # disperse l'escouade (siffle le disband)
}

# ====================================================================
# USEFUL ITEMS
# ====================================================================
# Items "Useful" (amelioration). Appliques en jeu par le client.
USEFUL_ITEMS: dict[str, int] = {
    # Desactive definitivement le trebuchement des Pikmin quand recu.
    # Utilise uniquement quand l'option Disable Pikmin Trip = "item".
    "Trip Immunity": 71823,
}

TRIP_IMMUNITY_ITEM_ID = USEFUL_ITEMS["Trip Immunity"]

# Nom de piece -> model ID (fourCC) du Pellet in-game (enum UfoPartID,
# include/Pellet.h). Sert a retrouver le Pellet physique d'une piece dans le
# niveau pour le faire disparaitre quand la location est validee cote serveur.
PART_MODEL_ID: dict[str, bytes] = {
    "Bowsprit":            b"ust1",
    "Gluon Drive":         b"ust2",
    "Anti-Dioxin Filter":  b"ust3",
    "Eternal Fuel Dynamo": b"ust4",
    "Main Engine":         b"ust5",
    "Whimsical Radar":     b"uf01",
    "Interstellar Radio":  b"uf02",
    "Guard Satellite":     b"uf03",
    "Chronos Reactor":     b"uf04",
    "Radiation Canopy":    b"uf05",
    "Geiger Counter":      b"uf06",
    "Sagittarius":         b"uf07",
    "Libra":               b"uf08",
    "Omega Stabilizer":    b"uf09",
    "#1 Ionium Jet":       b"uf10",
    "#2 Ionium Jet":       b"uf11",
    "Shock Absorber":      b"un01",
    "Gravity Jumper":      b"un02",
    "Pilot's Seat":        b"un03",
    "Nova Blaster":        b"un04",
    "Automatic Gear":      b"un05",
    "Zirconium Rotor":     b"un06",
    "Extraordinary Bolt":  b"un07",
    "Repair-type Bolt":    b"un08",
    "Space Float":         b"un09",
    "Massage Machine":     b"un10",
    "Secret Safe":         b"un11",
    "Positron Generator":  b"un12",
    "Analog Computer":     b"un13",
    "UV Lamp":             b"un14",
}


# Nom d'item -> type interne, pour le client.
TRAP_KINDS: dict[str, str] = {
    "Time Trap":       "time",
    "End Day Trap":    "end_day",
    "Damage Trap":     "damage",
    "Teleport Trap":   "teleport",
    "Disbanding Trap": "disband",
}


# ====================================================================
# PIKMIN LOCATIONS - Complete mapping of all possible Pikmin locations
# to their AP IDs. Generated sequentially starting from 71500.
# Format: "Color Pikmin: threshold": AP_ID
# ====================================================================

PIKMIN_LOCATIONS_MAP: Dict[str, int] = {}

# Generate all Pikmin location IDs (300 total: 100 per color)
_next_id = 71500
for _color in ["Red", "Yellow", "Blue"]:
    for _threshold in range(1, 101):
        _location_name = f"{_color} Pikmin: {_threshold}"
        PIKMIN_LOCATIONS_MAP[_location_name] = _next_id
        _next_id += 1

# Clean up temporary variables
del _next_id, _color, _threshold, _location_name


# ====================================================================
# Noms des locations de pieces de vaisseau
# ====================================================================
# Format : "<abrev zone> - <nom piece>", ex. "TDS - Bowsprit".
# AREA_ABBREV est l'unique source de verite : ne renommer une zone qu'ici.

AREA_ABBREV: Dict[str, str] = {
    "The Impact Site":    "TIS",
    "The Forest of Hope": "TFoH",
    "The Forest Navel":   "TFN",
    "The Distant Spring": "TDS",
    "The Final Trial":    "TFT",
}

# Zone -> stageID (enum StageID, GlobalGameOptions.h). Sert au comptage des
# etoiles par niveau (PlayerState.mStagePartsCollected) quand une piece est
# validee cote serveur.
AREA_STAGE_ID: Dict[str, int] = {
    "The Impact Site":    0,   # STAGE_Practice
    "The Forest of Hope": 1,   # STAGE_Forest
    "The Forest Navel":   2,   # STAGE_Cave
    "The Distant Spring": 3,   # STAGE_Yakushima
    "The Final Trial":    4,   # STAGE_Last
}

# Pieces qui donnent une capacite au vaisseau (PlayerState.mShipEffectPartFlag) :
# nom -> bit. Radar = bit 0, jets ioniques = bits 1 et 2.
SHIP_EFFECT_PARTS: Dict[str, int] = {
    "Whimsical Radar": 0x01,
    "#1 Ionium Jet":   0x02,
    "#2 Ionium Jet":   0x04,
}


def ship_part_location_name(part_name: str) -> str:
    """Nom de la location d'une piece, prefixe par l'abreviation de sa zone."""
    return f"{AREA_ABBREV[ALL_PARTS[part_name].area]} - {part_name}"


# ====================================================================
# ALL_LOCATIONS - Complete mapping of all locations (ship parts + pikmin)
# ====================================================================

ALL_LOCATIONS: Dict[str, int] = {
    # Ship part locations
    **{ship_part_location_name(name): data.ap_id for name, data in ALL_PARTS.items()},
    # Pikmin locations
    **PIKMIN_LOCATIONS_MAP,
}