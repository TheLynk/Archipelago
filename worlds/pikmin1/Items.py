import typing
from BaseClasses import Item, ItemClassification
from dataclasses import dataclass


@dataclass
class PikminItemData:
    code: int
    classification: ItemClassification
    progression: bool = False


class PikminItem(Item):
    game: str = "Pikmin 1"


# Base item ID for Pikmin 1
base_id = 0x500000

# Item table
item_table: typing.Dict[str, PikminItemData] = {
    # Ship Parts (Progression Items)
    "Main Engine": PikminItemData(
        code=base_id + 1,
        classification=ItemClassification.progression,
        progression=True
    ),
    "Positron Generator": PikminItemData(
        code=base_id + 2,
        classification=ItemClassification.progression,
        progression=True
    ),
    "Eternal Fuel Dynamo": PikminItemData(
        code=base_id + 3,
        classification=ItemClassification.progression,
        progression=True
    ),
    
    # Useful Items
    "Red Pikmin Seeds": PikminItemData(
        code=base_id + 50,
        classification=ItemClassification.useful
    ),
    "Blue Pikmin Seeds": PikminItemData(
        code=base_id + 51,
        classification=ItemClassification.useful
    ),
    "Yellow Pikmin Seeds": PikminItemData(
        code=base_id + 52,
        classification=ItemClassification.useful
    ),
    
    # Filler Items
    "Pellet": PikminItemData(
        code=base_id + 100,
        classification=ItemClassification.filler
    ),
    "Nectar": PikminItemData(
        code=base_id + 101,
        classification=ItemClassification.filler
    ),
}

# Filler item for filling extra slots
filler_item_name = "Pellet"

# All item names
item_names = frozenset(item_table.keys())
