"""
Items pour Pikmin 1 GameCube PAL
"""

from typing import Dict, NamedTuple, Optional
from BaseClasses import Item, ItemClassification


class ItemData(NamedTuple):
    code: Optional[int]
    classification: ItemClassification


class PikminItem(Item):
    game: str = "Pikmin"


# Base item code - doit être unique par monde
base_id = 0x1000000  # Exemple d'ID de base


item_table: Dict[str, ItemData] = {
    # Items de progression principaux
    "Red Pikmin Sprout": ItemData(base_id + 1, ItemClassification.progression),
    "Yellow Pikmin Sprout": ItemData(base_id + 2, ItemClassification.progression),
    "Blue Pikmin Sprout": ItemData(base_id + 3, ItemClassification.progression),
    
    # Items utiles
    "Pellet Posy": ItemData(base_id + 10, ItemClassification.useful),
    "Nectar": ItemData(base_id + 11, ItemClassification.useful),
    "Flower": ItemData(base_id + 12, ItemClassification.useful),
    
    # Items de remplissage
    "Pellet": ItemData(base_id + 20, ItemClassification.filler),
    "Small Pellet": ItemData(base_id + 21, ItemClassification.filler),
    "Medium Pellet": ItemData(base_id + 22, ItemClassification.filler),
    "Large Pellet": ItemData(base_id + 23, ItemClassification.filler),
}


# Créer le dictionnaire nom -> ID
item_name_to_id: Dict[str, int] = {name: data.code for name, data in item_table.items() if data.code is not None}


def get_item_by_name(name: str) -> ItemData:
    """Obtenir les données d'un item par son nom"""
    return item_table[name]