from dataclasses import dataclass
from BaseClasses import Item, ItemClassification
from typing import Dict

@dataclass
class PikminItemData:
    """Data for a Pikmin item"""
    id: int
    classification: ItemClassification
    max_quantity: int = 1

class PikminItem(Item):
    """Pikmin item implementation"""
    game = "Pikmin"

# Table des items pour Pikmin
item_table: Dict[str, PikminItemData] = {
    # Graines de Pikmin
    "Red Pikmin Seed": PikminItemData(
        id=12000,
        classification=ItemClassification.progression,
        max_quantity=100
    ),
    "Yellow Pikmin Seed": PikminItemData(
        id=12001,
        classification=ItemClassification.progression,
        max_quantity=100
    ),
    "Blue Pikmin Seed": PikminItemData(
        id=12002,
        classification=ItemClassification.progression,
        max_quantity=100
    ),
    
    # Items utiles
    "Pellet Posy": PikminItemData(
        id=12010,
        classification=ItemClassification.useful,
        max_quantity=50
    ),
    "Nectar": PikminItemData(
        id=12011,
        classification=ItemClassification.useful,
        max_quantity=20
    ),
    
    # Pièces de vaisseau (progression)
    "Ship Part": PikminItemData(
        id=12020,
        classification=ItemClassification.progression_skip_balancing,
        max_quantity=30
    ),
    "Engine": PikminItemData(
        id=12021,
        classification=ItemClassification.progression
    ),
    "Main Engine": PikminItemData(
        id=12022,
        classification=ItemClassification.progression
    ),
    
    # Capacités spéciales
    "Pikmin Whistle Range": PikminItemData(
        id=12030,
        classification=ItemClassification.useful
    ),
    "Pikmin Throw Power": PikminItemData(
        id=12031,
        classification=ItemClassification.useful
    ),
    
    # Items de remplissage
    "Pikmin Treat": PikminItemData(
        id=12040,
        classification=ItemClassification.filler,
        max_quantity=10
    )
}

# Items de progression requis
progression_items = [
    "Red Pikmin Seed",
    "Yellow Pikmin Seed", 
    "Blue Pikmin Seed",
    "Ship Part",
    "Engine",
    "Main Engine"
]