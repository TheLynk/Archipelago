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
    "Repair-Type Bolt": ShipPartData(71423, mem(0x81241414, 0x812489FC), 2, RequiredTypes(False, False, True), "The Distant Spring"), # un08
    "Space Float": ShipPartData(71424, mem(0x812414F4, 0x81248ADC), 2, RequiredTypes(False, False, False), "The Forest Navel"), # un09
    "Massage Machine": ShipPartData(71425, mem(0x812415D4, 0x81248BBC), 2, RequiredTypes(False, False, True), "The Distant Spring"), # un10
    "Secret Safe": ShipPartData(71426, mem(0x812416B4, 0x81248C9C), 2, RequiredTypes(True, True, True), "The Final Trial"), # un11
    "Positron Generator": ShipPartData(71427, mem(0x81241794, 0x81248D7C), 2, RequiredTypes(False, True, True), "The Impact Site"), # un12
    "Analog Computer": ShipPartData(71428, mem(0x81241874, 0x81248E5C), 2, RequiredTypes(True, False, True), "The Forest Navel"), # un13
    "UV Lamp": ShipPartData(71429, mem(0x81241954, 0x81248F3C), 2, RequiredTypes(False, True, False), "The Distant Spring"), # un14
}


# ====================================================================
# FILLER ITEMS - Dummy items to balance locations and items during
# randomizer generation. They don't affect gameplay on the emulator.
# ====================================================================

FILLER_ITEMS: Dict[str, None] = {
    "Carrot Pikpik": None,
}