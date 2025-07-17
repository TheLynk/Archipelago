"""
Pikmin 1 GameCube PAL APWorld
Un prototype simple pour Archipelago
"""

from typing import Dict, List, NamedTuple, Optional, Set, TYPE_CHECKING
from BaseClasses import Item, ItemClassification, Location, Tutorial
from worlds.AutoWorld import WebWorld, World
from .Items import PikminItem, item_table, item_name_to_id
from .Locations import PikminLocation, location_table, location_name_to_id
from .Rules import set_rules

if TYPE_CHECKING:
    from BaseClasses import MultiWorld

class PikminWebWorld(WebWorld):
    theme = "ocean"
    
    setup_en = Tutorial(
        "Multiworld Setup Tutorial",
        "A guide to setting up the Pikmin randomizer connected to an Archipelago Multiworld",
        "English",
        "setup_en.md",
        "setup/en",
        ["TheLynk"]
    )
    
    setup_fr = Tutorial(
        "Guide de configuration Multiworld",
        "Un guide pour configurer le randomizer Pikmin connecté à un Multiworld Archipelago",
        "Français",
        "setup_fr.md",
        "setup/fr",
        ["TheLynk"]
    )
    
    tutorials = [setup_en, setup_fr]


class PikminWorld(World):
    """
    Pikmin 1 GameCube PAL pour Archipelago
    """
    
    game = "Pikmin"
    topology_present = False
    data_version = 1
    
    item_name_to_id = item_name_to_id
    location_name_to_id = location_name_to_id
    
    web = PikminWebWorld()
    
    def __init__(self, multiworld: "MultiWorld", player: int):
        super().__init__(multiworld, player)
        
    def create_items(self) -> None:
        """Créer les items pour ce monde"""
        # Créer les items principaux
        itempool = []
        
        # Exemple d'items - à adapter selon vos besoins
        itempool.append(self.create_item("Red Pikmin Sprout"))
        itempool.append(self.create_item("Yellow Pikmin Sprout"))
        itempool.append(self.create_item("Blue Pikmin Sprout"))
        itempool.append(self.create_item("Pellet Posy"))
        itempool.append(self.create_item("Nectar"))
        
        # Ajouter des items de remplissage si nécessaire
        while len(itempool) < len(location_table):
            itempool.append(self.create_item("Pellet"))
        
        self.multiworld.itempool += itempool
        
    def create_regions(self) -> None:
        """Créer les régions du jeu"""
        from .Regions import create_regions
        create_regions(self)
        
    def create_item(self, name: str) -> Item:
        """Créer un item spécifique"""
        item_data = item_table[name]
        return PikminItem(name, item_data.classification, item_data.code, self.player)
    
    def set_rules(self) -> None:
        """Définir les règles de logique"""
        set_rules(self)
        
    def fill_slot_data(self) -> Dict[str, any]:
        """Données à envoyer au client"""
        return {
            "red_pikmin_address": 0x803D6CF7,
            "death_link": False,  # Peut être ajouté plus tard
        }
        
    def get_filler_item_name(self) -> str:
        """Item de remplissage par défaut"""
        return "Pellet"