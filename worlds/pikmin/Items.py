from collections.abc import Iterable
from typing import TYPE_CHECKING, NamedTuple, Optional

from BaseClasses import Item
from BaseClasses import ItemClassification as IC
from worlds.AutoWorld import World

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
        base_id: int = 2322432
        return base_id + code

ITEM_TABLE: dict[str, PikminItemData] = {
    "Red Pikmin":                 PikminItemData("Item",      IC.useful,                       0,  1, 0x20),
    "Victory":                   PikminItemData("Event",     IC.progression,               None,  1, None),
}