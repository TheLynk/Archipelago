# pyright: reportMissingImports=false
from collections.abc import Iterable
from typing import TYPE_CHECKING, NamedTuple, Optional

from BaseClasses import Item
from BaseClasses import ItemClassification as IC
from worlds.AutoWorld import World

def item_factory(items: str | Iterable[str], world: World) -> Item | list[Item]:
    """
    Create items based on their names.
    Depending on the input, this function can return a single item or a list of items.

    :param items: The name or names of the items to create.
    :param world: The game world.
    :raises KeyError: If an unknown item name is provided.
    :return: A single item or a list of items.
    """
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
    """
    This class represents the data for an item in Pikmin.

    :param type: The type of the item (e.g., "Item", "Ship Part").
    :param classification: The item's classification (progression, useful, filler).
    :param code: The unique code identifier for the item.
    :param quantity: The number of this item available.
    :param item_id: The ID used to represent the item in-game.
    """

    type: str
    classification: IC
    code: Optional[int]
    quantity: int
    item_id: Optional[int]

class PikminItem(Item):
    """
    This class represents an item in Pikmin.

    :param name: The item's name.
    :param player: The ID of the player who owns the item.
    :param data: The data associated with this item.
    :param classification: Optional classification to override the default.
    """

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
        """
        Compute the Archipelago ID for the given item code.

        :param code: The unique code for the item.
        :return: The computed Archipelago ID.
        """
        base_id: int = 159159
        return base_id + code

ITEM_TABLE: dict[str, PikminItemData] = {
    #Ship Part
    "Main Engine":                      PikminItemData("Item",      IC.progression,               0, 1,None),

    #New Area
    "The Impact Site":                  PikminItemData("Item",      IC.progression,               30, 1,None),
    "The Forest Of Hope":               PikminItemData("Item",      IC.progression,               31, 1,None),
    "The Forest Navel":                 PikminItemData("Item",      IC.progression,               32, 1,None),
    "The Distant Spring":               PikminItemData("Item",      IC.progression,               33, 1,None),
    "The Final Trial":                  PikminItemData("Item",      IC.progression,               34, 1,None),

    #Pikmin
    "Unlock Red Pikmin":                PikminItemData("Item",      IC.progression,               35,  1, 0x81242804),
    "Unlock Yellow Pikmin":             PikminItemData("Item",      IC.progression,               36,  1, 0x81242804),
    "Unlock Blue Pikmin":               PikminItemData("Item",      IC.progression,               37,  1, 0x81242804),

    #Filler
    "Carrot Pikpik":                    PikminItemData("Item",      IC.filler,                    38,  1, None),
    "Nectar":                           PikminItemData("Item",      IC.filler,                    39,  1, None),

    #Goal
    "Victory":                          PikminItemData("Event",     IC.progression,               None,  1, None),
}