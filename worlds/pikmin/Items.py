from collections.abc import Iterable
from typing import TYPE_CHECKING, NamedTuple, Optional

from BaseClasses import Item
from BaseClasses import ItemClassification as IC
from worlds.AutoWorld import World

def item_factory(items: str | Iterable[str], world: World) -> Item | list[Item]:
    """Create items based on their names."""
    ret: list[Item] = []
    singleton = False
    if isinstance(items, str):
        items = [items]
        singleton = True
    for item in items:
        if item in ITEM_TABLE:
            ret.append(world.create_item(item))
        else:
            raise KeyError(f"Unknown item {item}")

    return ret[0] if singleton else ret

class PikminItemData(NamedTuple):
    """Data for an item in Pikmin."""
    type: str
    classification: IC
    code: Optional[int]
    quantity: int
    item_id: Optional[int]

class PikminItem(Item):
    """Item class for Pikmin."""
    game: str = "Pikmin"
    type: Optional[str]

    def __init__(self, name: str, player: int, data: PikminItemData, classification: Optional[IC] = None) -> None:
        super().__init__(
            name,
            data.classification if classification is None else classification,
            None if data.code is None else PikminItem.get_apid(data.code),
            player,
        )
        self.type = data.type
        self.item_id = data.item_id

    @staticmethod
    def get_apid(code: int) -> int:
        """Compute the Archipelago ID for the given item code."""
        base_id: int = 159159
        return base_id + code

# Table d'items étendue
ITEM_TABLE: dict[str, PikminItemData] = {
    # === PROGRESSION ITEMS ===
    
    # Ship Parts - Critical Path
    "Main Engine":          PikminItemData("Ship Part", IC.progression, 0, 1, None),
    "Positron Generator":   PikminItemData("Ship Part", IC.progression, 1, 1, None),
    "Eternal Fuel Dynamo":  PikminItemData("Ship Part", IC.progression, 2, 1, None),
    "Extraordinary Bolt":   PikminItemData("Ship Part", IC.progression, 3, 1, None),
    "Whimsical Radar":      PikminItemData("Ship Part", IC.progression, 4, 1, None),
    "Geiger Counter":       PikminItemData("Ship Part", IC.progression, 5, 1, None),
    "Radiation Canopy":     PikminItemData("Ship Part", IC.progression, 6, 1, None),
    "Sagittarius":          PikminItemData("Ship Part", IC.progression, 7, 1, None),
    "Shock Absorber":       PikminItemData("Ship Part", IC.progression, 8, 1, None),
    "Automatic Gear":       PikminItemData("Ship Part", IC.progression, 9, 1, None),
    "#1 Ionium Jet":        PikminItemData("Ship Part", IC.progression, 10, 1, None),
    "Anti-Dioxin Filter":   PikminItemData("Ship Part", IC.progression, 11, 1, None),
    "Omega Stabilizer":     PikminItemData("Ship Part", IC.progression, 12, 1, None),
    "Gravity Jumper":       PikminItemData("Ship Part", IC.progression, 13, 1, None),
    "Analog Computer":      PikminItemData("Ship Part", IC.progression, 14, 1, None),
    "Guard Satellite":      PikminItemData("Ship Part", IC.progression, 15, 1, None),
    "Libra":                PikminItemData("Ship Part", IC.progression, 16, 1, None),
    "Repair-type Bolt":     PikminItemData("Ship Part", IC.progression, 17, 1, None),
    "Gluon Drive":          PikminItemData("Ship Part", IC.progression, 18, 1, None),
    "Zirconium Rotor":      PikminItemData("Ship Part", IC.progression, 19, 1, None),
    "Interstellar Radio":   PikminItemData("Ship Part", IC.progression, 20, 1, None),
    "Pilot's Seat":         PikminItemData("Ship Part", IC.progression, 21, 1, None),
    "#2 Ionium Jet":        PikminItemData("Ship Part", IC.progression, 22, 1, None),
    "Bowsprit":             PikminItemData("Ship Part", IC.progression, 23, 1, None),
    "Chronos Reactor":      PikminItemData("Ship Part", IC.progression, 24, 1, None),

    # Ship Parts - Optional but Useful
    "Nova Blaster":         PikminItemData("Ship Part", IC.useful, 25, 1, None),
    "Space Float":          PikminItemData("Ship Part", IC.useful, 26, 1, None),
    "Massage Machine":      PikminItemData("Ship Part", IC.useful, 27, 1, None),
    "UV Lamp":              PikminItemData("Ship Part", IC.useful, 28, 1, None),
    "Secret Safe":          PikminItemData("Ship Part", IC.useful, 29, 1, None),
    
    # Area Unlocks - Critical for progression
    "The Impact Site":      PikminItemData("Area", IC.progression, 30, 1, None),
    "The Forest Of Hope":   PikminItemData("Area", IC.progression, 31, 1, None),
    "The Forest Navel":     PikminItemData("Area", IC.progression, 32, 1, None),
    "The Distant Spring":   PikminItemData("Area", IC.progression, 33, 1, None),
    "The Final Trial":      PikminItemData("Area", IC.progression, 34, 1, None),

    # Pikmin Types - Essential for progression
    "Unlock Red Pikmin":    PikminItemData("Pikmin Type", IC.progression, 35, 1, 0x81242804),
    "Unlock Yellow Pikmin": PikminItemData("Pikmin Type", IC.progression, 36, 1, 0x81242804),
    "Unlock Blue Pikmin":   PikminItemData("Pikmin Type", IC.progression, 37, 1, 0x81242804),
    
    # Food Items (thematic filler)
    "Carrot Pikpik":        PikminItemData("Food", IC.filler, 72, 22, None),
    
    # === VICTORY ITEM ===
    "Victory": PikminItemData("Event", IC.progression, None, 1, None),
}

# Groupes d'items pour faciliter la configuration
SHIP_PART_ITEMS = {name for name, data in ITEM_TABLE.items() if data.type == "Ship Part"}
AREA_ITEMS = {name for name, data in ITEM_TABLE.items() if data.type == "Area"}
PIKMIN_TYPE_ITEMS = {name for name, data in ITEM_TABLE.items() if data.type == "Pikmin Type"}
UPGRADE_ITEMS = {name for name, data in ITEM_TABLE.items() if data.type == "Upgrade"}
CONSUMABLE_ITEMS = {name for name, data in ITEM_TABLE.items() if data.type == "Consumable"}
TRAP_ITEMS = {name for name, data in ITEM_TABLE.items() if data.type == "Trap"}

# Groupes par classification
PROGRESSION_ITEMS = {name for name, data in ITEM_TABLE.items() if IC.progression in data.classification}
USEFUL_ITEMS = {name for name, data in ITEM_TABLE.items() if IC.useful in data.classification}
FILLER_ITEMS = {name for name, data in ITEM_TABLE.items() if IC.filler in data.classification}

# Item name groups pour les options YAML
item_name_groups = {
    "Ship Parts": SHIP_PART_ITEMS,
    "Areas": AREA_ITEMS,
    "Pikmin Types": PIKMIN_TYPE_ITEMS,
    "Upgrades": UPGRADE_ITEMS,
    "Consumables": CONSUMABLE_ITEMS,
    "Traps": TRAP_ITEMS,
    "Progression": PROGRESSION_ITEMS,
    "Useful": USEFUL_ITEMS,
    "Filler": FILLER_ITEMS,
}