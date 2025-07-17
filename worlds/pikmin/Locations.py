"""
Définition des emplacements pour le monde Pikmin
"""

from typing import Dict, NamedTuple, Optional, List
from BaseClasses import Location
from enum import Enum


class PikminLocation(Location):
    """Classe pour les emplacements Pikmin"""
    game = "Pikmin"
    
    def __init__(self, player: int, name: str, address: Optional[int], parent):
        super().__init__(player, name, address, parent)
        self.area = getattr(parent, 'name', 'Unknown')


class LocationData(NamedTuple):
    """Structure de données pour un emplacement"""
    id: int
    area: str
    description: str = ""
    requires_item: Optional[str] = None
    requires_pikmin: Optional[str] = None
    day_available: int = 1


# ID de base pour les emplacements Pikmin
PIKMIN_BASE_LOCATION_ID = 5000000

# Zones du jeu
class Areas(Enum):
    IMPACT_SITE = "The Impact Site"
    FOREST_HOPE = "The Forest of Hope"
    FOREST_NAVEL = "The Forest Navel"
    DISTANT_SPRING = "The Distant Spring"
    FINAL_TRIAL = "The Final Trial"


# Table des emplacements
location_table: Dict[str, LocationData] = {}

current_id = PIKMIN_BASE_LOCATION_ID

# ===== THE IMPACT SITE =====
impact_site_locations = [
    ("Engine - Impact Site", "Moteur principal du vaisseau", None, None, 1),
    ("Positron Generator - Impact Site", "Générateur de positrons", None, None, 1),
    ("Red Pikmin Onion - Impact Site", "Découverte des Pikmin rouges", None, None, 1),
    ("Pellet Posy 1 - Impact Site", "Première fleur à pastille", None, None, 1),
    ("Pellet Posy 5 - Impact Site", "Fleur à pastille de 5", None, None, 1),
    ("Pellet Posy 10 - Impact Site", "Fleur à pastille de 10", None, None, 1),
    ("Breadbug Nest - Impact Site", "Nid de Breadbug", None, None, 1),
    ("Eternal Fuel Dynamo - Impact Site", "Dynamo de carburant éternel", None, "Red Pikmin", 1),
]

for name, description, requires_item, requires_pikmin, day in impact_site_locations:
    location_table[name] = LocationData(
        current_id,
        Areas.IMPACT_SITE.value,
        description,
        requires_item,
        requires_pikmin,
        day
    )
    current_id += 1

# ===== THE FOREST OF HOPE =====
forest_hope_locations = [
    ("Radiation Canopy - Forest of Hope", "Verrière de radiation", "Forest of Hope Access", "Red Pikmin", 2),
    ("Geiger Counter - Forest of Hope", "Compteur Geiger", "Forest of Hope Access", "Red Pikmin", 2),
    ("Extraordinary Bolt - Forest of Hope", "Boulon extraordinaire", "Forest of Hope Access", "Red Pikmin", 2),
    ("Nova Blaster - Forest of Hope", "Blaster Nova", "Forest of Hope Access", "Red Pikmin", 2),
    ("Sagittarius - Forest of Hope", "Sagittaire", "Forest of Hope Access", "Red Pikmin", 2),
    ("Libra - Forest of Hope", "Balance", "Forest of Hope Access", "Red Pikmin", 2),
    ("Bowsprit - Forest of Hope", "Beaupré", "Forest of Hope Access", "Red Pikmin", 2),
    ("Chronos Reactor - Forest of Hope", "Réacteur Chronos", "Forest of Hope Access", "Red Pikmin", 2),
    ("Yellow Pikmin Onion - Forest of Hope", "Découverte des Pikmin jaunes", "Forest of Hope Access", None, 2),
    ("Forest of Hope Bridge", "Construction du pont", "Forest of Hope Access", "Yellow Pikmin", 2),
    ("Burrowing Snagret - Forest of Hope", "Snagret fouisseur", "Forest of Hope Access", "Yellow Pikmin", 2),
    ("Spotty Bulbear - Forest of Hope", "Bulbear tacheté", "Forest of Hope Access", "Red Pikmin", 2),
    ("Armored Cannon Beetle - Forest of Hope", "Scarabée canon blindé", "Forest of Hope Access", "Yellow Pikmin", 2),
    ("Pellet Posy Garden - Forest of Hope", "Jardin de fleurs à pastilles", "Forest of Hope Access", None, 2),
    ("Nectar Weed 1 - Forest of Hope", "Herbe à nectar 1", "Forest of Hope Access", None, 2),
    ("Nectar Weed 2 - Forest of Hope", "Herbe à nectar 2", "Forest of Hope Access", None, 2),
    ("Nectar Weed 3 - Forest of Hope", "Herbe à nectar 3", "Forest of Hope Access", None, 2),
]

for name, description, requires_item, requires_pikmin, day in forest_hope_locations:
    location_table[name] = LocationData(
        current_id,
        Areas.FOREST_HOPE.value,
        description,
        requires_item,
        requires_pikmin,
        day
    )
    current_id += 1

# ===== THE FOREST NAVEL =====
forest_navel_locations = [
    ("Automatic Gear - Forest Navel", "Engrenage automatique", "Forest Navel Access", "Blue Pikmin", 8),
    ("Repair-type Bolt - Forest Navel", "Boulon de type réparation", "Forest Navel Access", "Blue Pikmin", 8),
    ("Shock Absorber - Forest Navel", "Amortisseur", "Forest Navel Access", "Blue Pikmin", 8),
    ("Analog Computer - Forest Navel", "Ordinateur analogique", "Forest Navel Access", "Blue Pikmin", 8),
    ("Whirlpool Generator - Forest Navel", "Générateur de tourbillon", "Forest Navel Access", "Blue Pikmin", 8),
    ("Interstellar Radio - Forest Navel", "Radio interstellaire", "Forest Navel Access", "Blue Pikmin", 8),
    ("Zirconium Rotor - Forest Navel", "Rotor de zirconium", "Forest Navel Access", "Blue Pikmin", 8),
    ("Blue Pikmin Onion - Forest Navel", "Découverte des Pikmin bleus", "Forest Navel Access", None, 8),
    ("Smoky Progg - Forest Navel", "Progg fumant", "Forest Navel Access", "Blue Pikmin", 15),
    ("Beady Long Legs - Forest Navel", "Longues pattes perlées", "Forest Navel Access", "Blue Pikmin", 8),
    ("Puffstool - Forest Navel", "Champignon bouffi", "Forest Navel Access", "Blue Pikmin", 8),
    ("Breadbug Nest 2 - Forest Navel", "Nid de Breadbug 2", "Forest Navel Access", None, 8),
    ("Underwater Treasure 1 - Forest Navel", "Trésor sous-marin 1", "Forest Navel Access", "Blue Pikmin", 8),
    ("Underwater Treasure 2 - Forest Navel", "Trésor sous-marin 2", "Forest Navel Access", "Blue Pikmin", 8),
    ("Underwater Treasure 3 - Forest Navel", "Trésor sous-marin 3", "Forest Navel Access", "Blue Pikmin", 8),
    ("Candypop Bud Red - Forest Navel", "Bourgeon Candypop rouge", "Forest Navel Access", None, 8),
    ("Candypop Bud Blue - Forest Navel", "Bourgeon Candypop bleu", "Forest Navel Access", None, 8),
    ("Candypop Bud Yellow - Forest Navel", "Bourgeon Candypop jaune", "Forest Navel Access", None, 8),
]

for name, description, requires_item, requires_pikmin, day in forest_navel_locations:
    location_table[name] = LocationData(
        current_id,
        Areas.FOREST_NAVEL.value,
        description,
        requires_item,
        requires_pikmin,
        day
    )
    current_id += 1

# ===== THE DISTANT SPRING =====
distant_spring_locations = [
    ("Pilot's Seat - Distant Spring", "Siège du pilote", "Distant Spring Access", "Yellow Pikmin", 11),
    ("Massage Girdle - Distant Spring", "Ceinture de massage", "Distant Spring Access", "Red Pikmin", 11),
    ("Gluon Drive - Distant Spring", "Moteur gluon", "Distant Spring Access", "Blue Pikmin", 11),
    ("Space Float - Distant Spring", "Flotteur spatial", "Distant Spring Access", "Blue Pikmin", 11),
    ("Magnetic Flux Controller - Distant Spring", "Contrôleur de flux magnétique", "Distant Spring Access", "Yellow Pikmin", 11),
    ("Gravity Jumper - Distant Spring", "Sauteur gravitationnel", "Distant Spring Access", "Red Pikmin", 11),
    ("Anti-Dioxin Filter - Distant Spring", "Filtre anti-dioxine", "Distant Spring Access", "Blue Pikmin", 11),
    ("UV Lamp - Distant Spring", "Lampe UV", "Distant Spring Access", "Yellow Pikmin", 11),
    ("Smoky Progg Egg - Distant Spring", "Œuf de Progg fumant", "Distant Spring Access", "Blue Pikmin", 15),
    ("Spotty Bulbear Alpha - Distant Spring", "Bulbear tacheté Alpha", "Distant Spring Access", "Red Pikmin", 11),
    ("Wollywog - Distant Spring", "Wollywog", "Distant Spring Access", "Blue Pikmin", 11),
    ("Yellow Wollywog - Distant Spring", "Wollywog jaune", "Distant Spring Access", "Blue Pikmin", 11),
    ("Water Dumple - Distant Spring", "Dumple d'eau", "Distant Spring Access", "Blue Pikmin", 11),
    ("Blowhog - Distant Spring", "Blowhog", "Distant Spring Access", "Red Pikmin", 11),
    ("Fiery Blowhog - Distant Spring", "Blowhog ardent", "Distant Spring Access", "Red Pikmin", 11),
    ("Watery Blowhog - Distant Spring", "Blowhog aqueux", "Distant Spring Access", "Blue Pikmin", 11),
    ("Honeywisp - Distant Spring", "Honeywisp", "Distant Spring Access", "Yellow Pikmin", 11),
    ("Iridescent Flint Beetle - Distant Spring", "Scarabée de silex iridescent", "Distant Spring Access", None, 11),
]

for name, description, requires_item, requires_pikmin, day in distant_spring_locations:
    location_table[name] = LocationData(
        current_id,
        Areas.DISTANT_SPRING.value,
        description,
        requires_item,
        requires_pikmin,
        day
    )
    current_id += 1

# ===== THE FINAL TRIAL =====
final_trial_locations = [
    ("Secret Safe - Final Trial", "Coffre-fort secret", "Final Trial Access", "Yellow Pikmin", 25),
    ("Cockpit - Final Trial", "Cockpit", "Final Trial Access", "Red Pikmin", 25),
    ("Fuel Tank - Final Trial", "Réservoir de carburant", "Final Trial Access", "Blue Pikmin", 25),
    ("Emperor Bulblax - Final Trial", "Empereur Bulblax", "Final Trial Access", "Yellow Pikmin", 25),
    ("Bulbmin Discovery - Final Trial", "Découverte des Bulbmin", "Final Trial Access", None, 25),
    ("Final Chamber Treasure 1 - Final Trial", "Trésor de la chambre finale 1", "Final Trial Access", "Yellow Pikmin", 25),
    ("Final Chamber Treasure 2 - Final Trial", "Trésor de la chambre finale 2", "Final Trial Access", "Blue Pikmin", 25),
    ("Final Chamber Treasure 3 - Final Trial", "Trésor de la chambre finale 3", "Final Trial Access", "Red Pikmin", 25),
    ("Hidden Alcove - Final Trial", "Alcôve cachée", "Final Trial Access", "Yellow Pikmin", 25),
    ("Emperor's Lair - Final Trial", "Repaire de l'Empereur", "Final Trial Access", "Yellow Pikmin", 25),
]

for name, description, requires_item, requires_pikmin, day in final_trial_locations:
    location_table[name] = LocationData(
        current_id,
        Areas.FINAL_TRIAL.value,
        description,
        requires_item,
        requires_pikmin,
        day
    )
    current_id += 1

# Emplacements spéciaux (événements)
special_locations = [
    ("Game Start", "Début du jeu", None, None, 1),
    ("First Pikmin", "Premier Pikmin découvert", None, None, 1),
    ("All Pikmin Types", "Tous les types de Pikmin découverts", None, None, 8),
    ("Half Ship Parts", "Moitié des pièces de vaisseau collectées", None, None, 15),
    ("Ship Repaired", "Vaisseau réparé", None, None, 30),
    ("Perfect Ending", "Fin parfaite", None, None, 30),
]

for name, description, requires_item, requires_pikmin, day in special_locations:
    location_table[name] = LocationData(
        current_id,
        "Special",
        description,
        requires_item,
        requires_pikmin,
        day
    )
    current_id += 1

# Vérification des IDs uniques
def validate_location_table():
    """Vérifie que tous les IDs sont uniques"""
    ids = [data.id for data in location_table.values()]
    if len(ids) != len(set(ids)):
        raise ValueError("IDs d'emplacements en double détectés!")
    
    # Vérifier que toutes les zones sont représentées
    areas_in_table = set(data.area for data in location_table.values())
    expected_areas = {area.value for area in Areas}
    expected_areas.add("Special")
    
    if not expected_areas.issubset(areas_in_table):
        missing = expected_areas - areas_in_table
        raise ValueError(f"Zones manquantes dans location_table: {missing}")

# Validation au chargement du module
validate_location_table()

# Fonctions utilitaires
def get_locations_by_area(area: str) -> List[str]:
    """Retourne tous les emplacements d'une zone"""
    return [name for name, data in location_table.items() if data.area == area]

def get_ship_part_locations() -> List[LocationData]:
    """Retourne tous les emplacements de pièces de vaisseau"""
    ship_part_keywords = ["Engine", "Generator", "Dynamo", "Radio", "Bowsprit", "Reactor", 
                         "Drive", "Rotor", "Gear", "Float", "Bolt", "Absorber", "Computer",
                         "Whirlpool", "Seat", "Girdle", "Canopy", "Jumper", "Sagittarius",
                         "Counter", "Libra", "Blaster", "Controller", "Filter", "Lamp", "Safe",
                         "Cockpit", "Tank"]
    
    return [data for name, data in location_table.items() 
            if any(keyword in name for keyword in ship_part_keywords)]

def get_progression_locations() -> List[str]:
    """Retourne les emplacements critiques pour la progression"""
    progression_keywords = ["Onion", "Engine", "Generator", "Radio", "Access"]
    return [name for name in location_table.keys() 
            if any(keyword in name for keyword in progression_keywords)]

def get_locations_requiring_pikmin(pikmin_type: str) -> List[str]:
    """Retourne les emplacements nécessitant un type de Pikmin spécifique"""
    return [name for name, data in location_table.items() 
            if data.requires_pikmin == pikmin_type]

def get_locations_by_day(day: int) -> List[str]:
    """Retourne les emplacements disponibles à partir d'un jour donné"""
    return [name for name, data in location_table.items() 
            if data.day_available <= day]

# Groupes d'emplacements pour la logique
ship_part_locations = get_ship_part_locations()
progression_locations = get_progression_locations()

# Mappings pour la facilité d'utilisation
location_name_to_id = {name: data.id for name, data in location_table.items()}
id_to_location_name = {data.id: name for name, data in location_table.items()}

# Statistiques
TOTAL_LOCATIONS = len(location_table)
SHIP_PART_COUNT = len(ship_part_locations)
PROGRESSION_COUNT = len(progression_locations)

# Vérifications finales
assert TOTAL_LOCATIONS > 0, "La table des emplacements est vide"
assert SHIP_PART_COUNT >= 29, f"Nombre insuffisant d'emplacements de pièces: {SHIP_PART_COUNT}"
assert len(get_locations_by_area(Areas.IMPACT_SITE.value)) > 0, "Pas d'emplacements dans Impact Site"
assert len(get_locations_by_area(Areas.FOREST_HOPE.value)) > 0, "Pas d'emplacements dans Forest of Hope"
assert len(get_locations_by_area(Areas.FOREST_NAVEL.value)) > 0, "Pas d'emplacements dans Forest Navel"
assert len(get_locations_by_area(Areas.DISTANT_SPRING.value)) > 0, "Pas d'emplacements dans Distant Spring"
assert len(get_locations_by_area(Areas.FINAL_TRIAL.value)) > 0, "Pas d'emplacements dans Final Trial"