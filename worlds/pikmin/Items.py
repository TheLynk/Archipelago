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
    "Main Engine": PikminItemData("Ship Part", IC.progression, 0, 1, None),
    "Positron Generator": PikminItemData("Ship Part", IC.progression, 1, 1, None),
    "Eternal Fuel Dynamo": PikminItemData("Ship Part", IC.progression, 2, 1, None),
    "Nova Blaster": PikminItemData("Ship Part", IC.progression, 3, 1, None),
    "Radiation Canopy": PikminItemData("Ship Part", IC.progression, 4, 1, None),
    "Geiger Counter": PikminItemData("Ship Part", IC.progression, 5, 1, None),
    "Gravity Jumper": PikminItemData("Ship Part", IC.progression, 6, 1, None),
    "Chronos Reactor": PikminItemData("Ship Part", IC.progression, 7, 1, None),
    "Gluon Drive": PikminItemData("Ship Part", IC.progression, 8, 1, None),
    "UV Lamp": PikminItemData("Ship Part", IC.progression, 9, 1, None),
    "Interstellar Radio": PikminItemData("Ship Part", IC.progression, 10, 1, None),
    "Secret Safe": PikminItemData("Ship Part", IC.progression, 11, 1, None),
    
    # Ship Parts - Optional but Useful
    "Whimsical Radar": PikminItemData("Ship Part", IC.useful, 12, 1, None),
    "Extraordinary Bolt": PikminItemData("Ship Part", IC.useful, 13, 1, None),
    "Bowsprit": PikminItemData("Ship Part", IC.useful, 14, 1, None),
    "Libra": PikminItemData("Ship Part", IC.useful, 15, 1, None),
    "Zirconium Rotor": PikminItemData("Ship Part", IC.useful, 16, 1, None),
    "Repair-type Bolt": PikminItemData("Ship Part", IC.useful, 17, 1, None),
    "Pilot's Seat": PikminItemData("Ship Part", IC.useful, 18, 1, None),
    
    # Area Unlocks - Critical for progression
    "The Impact Site": PikminItemData("Area", IC.progression, 30, 1, None),
    "The Forest Of Hope": PikminItemData("Area", IC.progression, 31, 1, None),
    "The Forest Navel": PikminItemData("Area", IC.progression, 32, 1, None),
    "The Distant Spring": PikminItemData("Area", IC.progression, 33, 1, None),
    "The Final Trial": PikminItemData("Area", IC.progression, 34, 1, None),

    # Pikmin Types - Essential for progression
    "Unlock Red Pikmin": PikminItemData("Pikmin Type", IC.progression, 35, 1, 0x81242804),
    "Unlock Yellow Pikmin": PikminItemData("Pikmin Type", IC.progression, 36, 1, 0x81242804),
    "Unlock Blue Pikmin": PikminItemData("Pikmin Type", IC.progression, 37, 1, 0x81242804),
    
    # === USEFUL ITEMS ===
    
    # Tools and Upgrades
    "Pikmin Whistle Range Up": PikminItemData("Upgrade", IC.useful, 50, 1, None),
    "Pikmin Throw Distance Up": PikminItemData("Upgrade", IC.useful, 51, 1, None),
    "Olimar Movement Speed Up": PikminItemData("Upgrade", IC.useful, 52, 1, None),
    "Extra Day Time": PikminItemData("Upgrade", IC.useful, 53, 1, None),
    "Pikmin Carrying Speed Up": PikminItemData("Upgrade", IC.useful, 54, 1, None),
    
    # Pikmin Boosts
    "Red Pikmin Boost": PikminItemData("Pikmin Boost", IC.useful, 55, 3, None),
    "Yellow Pikmin Boost": PikminItemData("Pikmin Boost", IC.useful, 56, 3, None),
    "Blue Pikmin Boost": PikminItemData("Pikmin Boost", IC.useful, 57, 3, None),
    "Mixed Pikmin Boost": PikminItemData("Pikmin Boost", IC.useful, 58, 5, None),
    
    # Resource Items
    "Pellet Pack Small": PikminItemData("Resource", IC.useful, 60, 10, None),
    "Pellet Pack Medium": PikminItemData("Resource", IC.useful, 61, 5, None),
    "Pellet Pack Large": PikminItemData("Resource", IC.useful, 62, 2, None),
    
    # === FILLER ITEMS ===
    
    # Basic Consumables
    "Nectar": PikminItemData("Consumable", IC.filler, 38, 20, None),
    "Ultra-Spicy Spray": PikminItemData("Consumable", IC.filler, 70, 10, None),
    "Ultra-Bitter Spray": PikminItemData("Consumable", IC.filler, 71, 10, None),
    
    # Food Items (thematic filler)
    "Carrot Pikpik": PikminItemData("Food", IC.filler, 72, 15, None),
    "Sunseed Berry": PikminItemData("Food", IC.filler, 73, 15, None),
    "Strawberry": PikminItemData("Food", IC.filler, 74, 10, None),
    "Pellet Posy": PikminItemData("Food", IC.filler, 75, 20, None),
    
    # Small Utility Items
    "Day Extension": PikminItemData("Utility", IC.filler, 76, 5, None),
    "Pikmin Seed": PikminItemData("Utility", IC.filler, 77, 25, None),
    "Flower Nectar": PikminItemData("Utility", IC.filler, 78, 15, None),
    
    # === TRAP ITEMS === (Optional - can add challenge)
    
    "Temporal Setback": PikminItemData("Trap", IC.trap, 80, 2, None),  # Lose a day
    "Pikmin Confusion": PikminItemData("Trap", IC.trap, 81, 3, None),  # Temporary control issues
    "Weather Disruption": PikminItemData("Trap", IC.trap, 82, 2, None),  # Bad weather effect
    
    # === SPECIAL ITEMS ===
    
    # Keys for special areas or challenges
    "Challenge Mode Key": PikminItemData("Key", IC.useful, 90, 1, None),
    "Time Attack Key": PikminItemData("Key", IC.useful, 91, 1, None),
    
    # Bonus Content
    "Picture Book Page": PikminItemData("Collectible", IC.filler, 92, 10, None),
    "Music Track": PikminItemData("Collectible", IC.filler, 93, 8, None),
    
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