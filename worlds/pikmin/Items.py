"""
Définition des objets pour le monde Pikmin
"""

from typing import Dict, NamedTuple, Optional, List
from BaseClasses import Item, ItemClassification


class PikminItem(Item):
    """Classe pour les objets Pikmin"""
    game = "Pikmin"
    
    def __init__(self, name: str, classification: ItemClassification, code: int, player: int):
        super().__init__(name, classification, code, player)


class ItemData(NamedTuple):
    """Structure de données pour un objet"""
    id: int
    classification: ItemClassification
    max_quantity: int = 1
    description: str = ""


# ID de base pour les objets Pikmin
PIKMIN_BASE_ID = 5000000

# Pièces de vaisseau (objets de progression) - Les 30 pièces du jeu original
ship_parts = [
    "Main Engine",
    "Positron Generator", 
    "Eternal Fuel Dynamo",
    "Interstellar Radio",
    "Bowsprit",
    "Chronos Reactor",
    "Gluon Drive",
    "Zirconium Rotor",
    "Automatic Gear",
    "Space Float",
    "Repair-type Bolt",
    "Shock Absorber",
    "Analog Computer",
    "Extraordinary Bolt",
    "Engine",
    "Whirlpool Generator",
    "Pilot's Seat",
    "Massage Girdle",
    "Radiation Canopy",
    "Gravity Jumper",
    "Sagittarius",
    "Geiger Counter",
    "Libra",
    "Nova Blaster",
    "Magnetic Flux Controller",
    "Anti-Dioxin Filter",
    "UV Lamp",
    "Secret Safe",
    "Cockpit",
    "Fuel Tank"
]

# Table des objets
item_table: Dict[str, ItemData] = {}

# Pièces de vaisseau critiques (nécessaires pour débloquer les zones)
critical_ship_parts = [
    "Main Engine",        # Requis pour décoller
    "Positron Generator", # Requis pour décoller
    "Eternal Fuel Dynamo" # Requis pour décoller
]

# Pièces de vaisseau pour déblocage de zones
area_unlock_parts = [
    "Interstellar Radio",  # Débloque communication
    "Bowsprit"            # Débloque navigation
]

# Pièces de vaisseau importantes (affectent la progression)
important_ship_parts = [
    "Chronos Reactor",
    "Gluon Drive", 
    "Zirconium Rotor",
    "Automatic Gear",
    "Space Float",
    "Repair-type Bolt",
    "Shock Absorber",
    "Analog Computer",
    "Extraordinary Bolt",
    "Engine",
    "Whirlpool Generator",
    "Pilot's Seat"
]

# Pièces de vaisseau optionnelles (pour le 100% mais pas requises)
optional_ship_parts = [
    "Massage Girdle",
    "Radiation Canopy", 
    "Gravity Jumper",
    "Sagittarius",
    "Geiger Counter",
    "Libra",
    "Nova Blaster",
    "Magnetic Flux Controller",
    "Anti-Dioxin Filter",
    "UV Lamp",
    "Secret Safe",
    "Cockpit",
    "Fuel Tank"
]

# Construction de la table des objets
current_id = PIKMIN_BASE_ID

# Pièces de vaisseau critiques
for i, part in enumerate(critical_ship_parts):
    item_table[part] = ItemData(
        current_id + i,
        ItemClassification.progression,
        1,
        f"Pièce critique du vaisseau: {part}"
    )

current_id += len(critical_ship_parts)

# Pièces de vaisseau pour déblocage de zones
for i, part in enumerate(area_unlock_parts):
    item_table[part] = ItemData(
        current_id + i,
        ItemClassification.progression,
        1,
        f"Pièce de déblocage: {part}"
    )

current_id += len(area_unlock_parts)

# Pièces de vaisseau importantes
for i, part in enumerate(important_ship_parts):
    item_table[part] = ItemData(
        current_id + i,
        ItemClassification.progression_skip_balancing,
        1,
        f"Pièce importante du vaisseau: {part}"
    )

current_id += len(important_ship_parts)

# Pièces de vaisseau optionnelles
for i, part in enumerate(optional_ship_parts):
    item_table[part] = ItemData(
        current_id + i,
        ItemClassification.useful,
        1,
        f"Pièce optionnelle du vaisseau: {part}"
    )

current_id += len(optional_ship_parts)

# Types de Pikmin (requis pour accéder à certaines zones)
pikmin_types = [
    ("Red Pikmin Discovery", ItemClassification.progression, "Débloque les Pikmin rouges (résistants au feu)"),
    ("Blue Pikmin Discovery", ItemClassification.progression, "Débloque les Pikmin bleus (peuvent nager)"),
    ("Yellow Pikmin Discovery", ItemClassification.progression, "Débloque les Pikmin jaunes (résistants à l'électricité)"),
]

for name, classification, description in pikmin_types:
    item_table[name] = ItemData(
        current_id,
        classification,
        1,
        description
    )
    current_id += 1

# Graines de Pikmin (objets utiles pour augmenter l'armée)
pikmin_seeds = [
    ("Red Pikmin Seeds", ItemClassification.useful, "Graines de Pikmin rouges"),
    ("Blue Pikmin Seeds", ItemClassification.useful, "Graines de Pikmin bleus"),
    ("Yellow Pikmin Seeds", ItemClassification.useful, "Graines de Pikmin jaunes"),
]

for name, classification, description in pikmin_seeds:
    item_table[name] = ItemData(
        current_id,
        classification,
        50,  # Quantité max
        description
    )
    current_id += 1

# Objets de déblocage de zones
area_unlocks = [
    ("Forest of Hope Access", ItemClassification.progression, "Accès à la Forêt de l'Espoir"),
    ("Forest Navel Access", ItemClassification.progression, "Accès au Nombril de la Forêt"),
    ("Distant Spring Access", ItemClassification.progression, "Accès à la Source Distante"),
    ("Final Trial Access", ItemClassification.progression, "Accès à l'Épreuve Finale"),
]

for name, classification, description in area_unlocks:
    item_table[name] = ItemData(
        current_id,
        classification,
        1,
        description
    )
    current_id += 1

# Améliorations et objets utilitaires
utility_items = [
    ("Pellet Posy", ItemClassification.filler, 1, "Petite fleur qui produit des pastilles"),
    ("Nectar", ItemClassification.filler, 1, "Nectar pour faire pousser les Pikmin"),
    ("Spicy Spray", ItemClassification.useful, 1, "Spray épicé pour améliorer les Pikmin"),
    ("Bitter Spray", ItemClassification.useful, 1, "Spray amer pour pétrifier les ennemis"),
    ("Bridge Kit", ItemClassification.progression, 1, "Kit pour construire des ponts"),
    ("Bomb Rock", ItemClassification.useful, 1, "Rocher explosif"),
    ("Candypop Bud", ItemClassification.useful, 1, "Bourgeon pour transformer les Pikmin"),
    ("Onion Upgrade", ItemClassification.progression, 1, "Amélioration d'Oignon"),
    ("Whistle Upgrade", ItemClassification.useful, 1, "Amélioration du sifflet"),
    ("Pluck Upgrade", ItemClassification.useful, 1, "Amélioration de la cueillette"),
    ("Throw Upgrade", ItemClassification.useful, 1, "Amélioration du lancer"),
    ("Health Upgrade", ItemClassification.useful, 1, "Amélioration de la santé d'Olimar"),
    ("Suit Upgrade", ItemClassification.progression, 1, "Amélioration de la combinaison"),
]

for name, classification, max_qty, description in utility_items:
    item_table[name] = ItemData(
        current_id,
        classification,
        max_qty,
        description
    )
    current_id += 1

# Objets piège (ennemis qui apparaissent)
trap_items = [
    ("Antenna Beetle", ItemClassification.trap, 1, "Scarabée d'antenne (confond les Pikmin)"),
    ("Wollywog", ItemClassification.trap, 1, "Wollywog (écrase les Pikmin)"),
    ("Blowhog", ItemClassification.trap, 1, "Blowhog (souffle les Pikmin)"),
    ("Bulborb", ItemClassification.trap, 1, "Bulborb (mange les Pikmin)"),
    ("Beady Long Legs", ItemClassification.trap, 1, "Beady Long Legs (boss piège)"),
]

for name, classification, max_qty, description in trap_items:
    item_table[name] = ItemData(
        current_id,
        classification,
        max_qty,
        description
    )
    current_id += 1

# Objets de temps
time_items = [
    ("Extra Day", ItemClassification.useful, "Jour supplémentaire"),
    ("Time Extension", ItemClassification.useful, "Extension de temps pour la journée"),
    ("Sunrise", ItemClassification.progression, "Débloque le lever du soleil"),
    ("Sunset Delay", ItemClassification.useful, "Retarde le coucher du soleil"),
]

for name, classification, description in time_items:
    item_table[name] = ItemData(
        current_id,
        classification,
        1,
        description
    )
    current_id += 1

# Objets de capacité
ability_items = [
    ("Group Move", ItemClassification.useful, "Capacité de déplacement en groupe"),
    ("Dismiss All", ItemClassification.useful, "Capacité de renvoyer tous les Pikmin"),
    ("Swarm", ItemClassification.useful, "Capacité d'essaim"),
    ("Charge", ItemClassification.useful, "Capacité de charge"),
    ("Call", ItemClassification.useful, "Capacité d'appel à distance"),
]

for name, classification, description in ability_items:
    item_table[name] = ItemData(
        current_id,
        classification,
        1,
        description
    )
    current_id += 1

# Vérification des IDs uniques
def validate_item_table():
    """Vérifie que tous les IDs sont uniques"""
    ids = [data.id for data in item_table.values()]
    if len(ids) != len(set(ids)):
        raise ValueError("IDs d'objets en double détectés!")
    
    # Vérifier que tous les ship_parts sont dans la table
    for part in ship_parts:
        if part not in item_table:
            raise ValueError(f"Pièce de vaisseau manquante dans item_table: {part}")

# Validation au chargement du module
validate_item_table()

# Fonctions utilitaires
def get_ship_part_items() -> List[str]:
    """Retourne tous les objets de pièces de vaisseau"""
    return [name for name in ship_parts if name in item_table]

def get_progression_items() -> List[str]:
    """Retourne tous les objets de progression"""
    return [name for name, data in item_table.items() 
            if data.classification == ItemClassification.progression]

def get_useful_items() -> List[str]:
    """Retourne tous les objets utiles"""
    return [name for name, data in item_table.items() 
            if data.classification == ItemClassification.useful]

def get_filler_items() -> List[str]:
    """Retourne tous les objets de remplissage"""
    return [name for name, data in item_table.items() 
            if data.classification == ItemClassification.filler]

def get_trap_items() -> List[str]:
    """Retourne tous les objets piège"""
    return [name for name, data in item_table.items() 
            if data.classification == ItemClassification.trap]

def get_items_by_area(area: str) -> List[str]:
    """Retourne les objets trouvables dans une zone spécifique"""
    # Cette fonction sera complétée quand les locations seront définies
    area_items = {
        "The Impact Site": ["Main Engine", "Positron Generator"],
        "The Forest of Hope": ["Eternal Fuel Dynamo", "Nova Blaster", "Radiation Canopy"],
        "The Forest Navel": ["Libra", "Geiger Counter", "Magnetic Flux Controller"],
        "The Distant Spring": ["Pilot's Seat", "Chronos Reactor", "Interstellar Radio"],
        "The Final Trial": ["Secret Safe", "Sagittarius", "Anti-Dioxin Filter"]
    }
    return area_items.get(area, [])

# Groupes d'objets pour la logique
CRITICAL_ITEMS = get_progression_items()
PIKMIN_DISCOVERY_ITEMS = ["Red Pikmin Discovery", "Blue Pikmin Discovery", "Yellow Pikmin Discovery"]
AREA_ACCESS_ITEMS = ["Forest of Hope Access", "Forest Navel Access", "Distant Spring Access", "Final Trial Access"]
SHIP_PART_ITEMS = get_ship_part_items()
CRITICAL_SHIP_PARTS = critical_ship_parts
OPTIONAL_SHIP_PARTS = optional_ship_parts

# Mappings pour la facilité d'utilisation
item_name_to_id = {name: data.id for name, data in item_table.items()}
id_to_item_name = {data.id: name for name, data in item_table.items()}

# Vérifications finales
assert len(item_table) > 0, "La table des objets est vide"
assert len(SHIP_PART_ITEMS) == 30, f"Nombre incorrect de pièces de vaisseau: {len(SHIP_PART_ITEMS)}"
assert all(part in item_table for part in ship_parts), "Toutes les pièces de vaisseau doivent être dans item_table"

print(f"Items.py chargé avec succès: {len(item_table)} objets définis")