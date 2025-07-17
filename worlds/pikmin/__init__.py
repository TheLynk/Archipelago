"""
APWorld pour Pikmin - Fichier principal
"""

from typing import Dict, List, Set, Tuple, Optional, Any
from BaseClasses import World, Region, Location, Item, Tutorial, ItemClassification
from worlds.AutoWorld import WebWorld
import logging

logger = logging.getLogger("Pikmin")

from .Items import PikminItem, item_table, ship_parts

try:
    from .Locations import PikminLocation, location_table, ship_part_locations
except ImportError:
    logger.warning("Locations module not found, using dummy data")
    location_table = {}
    ship_part_locations = []
    
    class PikminLocation(Location):
        def __init__(self, player: int, name: str, address: int, parent: Region):
            super().__init__(player, name, address, parent)

try:
    from .Rules import set_rules
except ImportError:
    logger.warning("Rules module not found, using dummy function")
    def set_rules(world):
        pass

from .Options import PikminOptions


class PikminWebWorld(WebWorld):
    """Interface web pour le monde Pikmin"""
    
    theme = "ocean"
    
    setup_en = Tutorial(
        "Multiworld Setup Tutorial",
        "A guide to setting up the Pikmin randomizer connected to an Archipelago Multiworld",
        "English",
        "setup_en.md",
        "setup/en",
        ["TheLynk"]
    )
    
    tutorials = [setup_en]


class PikminWorld(World):
    """Monde Pikmin pour Archipelago"""
    
    game = "Pikmin"
    web = PikminWebWorld()
    
    item_name_to_id = {name: data.id for name, data in item_table.items()} if item_table else {}
    location_name_to_id = {name: data.id for name, data in location_table.items()} if location_table else {}
    
    options_dataclass = PikminOptions
    options: PikminOptions
    
    required_client_version = (0, 4, 2)
    
    def __init__(self, world, player: int):
        super().__init__(world, player)
        self.locked_locations: Set[str] = set()
        self.ship_parts_collected: Set[str] = set()
        self.areas_unlocked: Set[str] = {"The Impact Site"}  # Zone de départ
    
    def create_regions(self):
        """Crée les régions du jeu"""
        
        # Région de départ (menu)
        menu_region = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu_region)
        
        # Zones du jeu
        areas = [
            "The Impact Site",
            "The Forest of Hope", 
            "The Forest Navel",
            "The Distant Spring",
            "The Final Trial"
        ]
        
        previous_region = menu_region
        
        for area_name in areas:
            # Créer la région
            area_region = Region(area_name, self.player, self.multiworld)
            self.multiworld.regions.append(area_region)
            
            # Ajouter les emplacements de cette zone si disponible
            if ship_part_locations:
                area_locations = [
                    loc for loc in ship_part_locations 
                    if hasattr(loc, 'area') and loc.area == area_name
                ]
                
                for location_data in area_locations:
                    location = PikminLocation(
                        self.player,
                        location_data.name,
                        location_data.id,
                        area_region
                    )
                    area_region.locations.append(location)
            
            # Créer l'entrée depuis la région précédente
            if previous_region:
                entrance = previous_region.connect(area_region, f"Go to {area_name}")
                # Les règles d'accès seront définies plus tard
            
            previous_region = area_region
    
    def create_items(self):
        """Crée les objets du jeu"""
        
        # Objets principaux (pièces de vaisseau)
        if ship_parts:
            for part_name in ship_parts:
                if part_name in item_table:
                    item_data = item_table[part_name]
                    item = PikminItem(
                        part_name,
                        item_data.classification,
                        item_data.id,
                        self.player
                    )
                    self.multiworld.itempool.append(item)
        
        # Objets utilitaires (Pikmin, améliorations, etc.)
        utility_items = [
            ("Red Pikmin Seeds", ItemClassification.useful, 10),
            ("Blue Pikmin Seeds", ItemClassification.useful, 10),
            ("Yellow Pikmin Seeds", ItemClassification.useful, 10),
            ("Pellet Posy", ItemClassification.filler, 20),
            ("Nectar", ItemClassification.filler, 15),
            ("Spicy Spray", ItemClassification.useful, 5),
            ("Bitter Spray", ItemClassification.useful, 5),
        ]
        
        for item_name, classification, count in utility_items:
            if item_name in item_table:
                item_data = item_table[item_name]
                for _ in range(count):
                    item = PikminItem(
                        item_name,
                        classification,
                        item_data.id,
                        self.player
                    )
                    self.multiworld.itempool.append(item)
    
    def set_rules(self):
        """Définit les règles d'accès pour les régions et emplacements"""
        set_rules(self)
    
    def create_item(self, name: str) -> Item:
        """Crée un objet par son nom"""
        if name not in item_table:
            raise ValueError(f"Objet inconnu: {name}")
        
        item_data = item_table[name]
        return PikminItem(
            name,
            item_data.classification,
            item_data.id,
            self.player
        )
    
    def get_filler_item_name(self) -> str:
        """Retourne le nom d'un objet de remplissage"""
        return "Pellet Posy"
    
    def fill_slot_data(self) -> Dict[str, Any]:
        """Données à envoyer au client"""
        return {
            "ship_parts": list(ship_parts) if ship_parts else [],
            "areas": list(self.areas_unlocked),
            "seed": self.multiworld.seed,
            "player_name": self.multiworld.player_name[self.player],
            "player_id": self.player,
        }
    
    def pre_fill(self):
        """Pré-remplissage avant la génération"""
        # Assurer que certains objets critiques sont placés logiquement
        pass
    
    def generate_early(self):
        """Génération précoce - appelée avant la logique principale"""
        logger.info(f"Génération du monde Pikmin pour le joueur {self.player}")
    
    def generate_basic(self):
        """Génération de base"""
        # Placer les objets de progression dans des endroits appropriés
        pass
    
    def post_fill(self):
        """Post-remplissage après la génération"""
        # Vérifications finales
        pass
    
    def modify_multidata(self, multidata: Dict[str, Any]):
        """Modifie les données multi-monde"""
        # Ajout de métadonnées spécifiques à Pikmin
        pass


# Définition des constantes pour les autres modules
PIKMIN_AREAS = [
    "The Impact Site",
    "The Forest of Hope", 
    "The Forest Navel",
    "The Distant Spring",
    "The Final Trial"
]

SHIP_PARTS_REQUIRED = {
    "The Forest of Hope": 1,
    "The Forest Navel": 5,
    "The Distant Spring": 12,
    "The Final Trial": 29
}


def launch():
    """Point d'entrée pour le lancement"""
    from Utils import init_logging
    init_logging("Pikmin")
    
    from worlds.LauncherComponents import launch_subprocess
    launch_subprocess()


if __name__ == "__main__":
    launch()