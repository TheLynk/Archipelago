from dataclasses import dataclass
from BaseClasses import Location
from typing import Dict, Optional

@dataclass
class PikminLocationData:
    """Data for a Pikmin location"""
    id: int
    region: str
    rule: Optional[str] = None

class PikminLocation(Location):
    """Pikmin location implementation"""
    game = "Pikmin"

# Table des emplacements pour Pikmin
location_table: Dict[str, PikminLocationData] = {
    # Zone d'impact (The Impact Site)
    "Impact Site - First Pellet": PikminLocationData(
        id=11000,
        region="Impact Site"
    ),
    "Impact Site - Red Pikmin Discovery": PikminLocationData(
        id=11001,
        region="Impact Site"
    ),
    "Impact Site - Main Engine": PikminLocationData(
        id=11002,
        region="Impact Site"
    ),
    
    # Forêt de l'Espoir (The Forest of Hope)
    "Forest of Hope - Entrance Pellet": PikminLocationData(
        id=11010,
        region="Forest of Hope"
    ),
    "Forest of Hope - Yellow Pikmin Discovery": PikminLocationData(
        id=11011,
        region="Forest of Hope"
    ),
    "Forest of Hope - Eternal Fuel Dynamo": PikminLocationData(
        id=11012,
        region="Forest of Hope"
    ),
    "Forest of Hope - Whimsical Radar": PikminLocationData(
        id=11013,
        region="Forest of Hope"
    ),
    
    # Caverne de la Flamme (The Forest Navel)
    "Forest Navel - Blue Pikmin Discovery": PikminLocationData(
        id=11020,
        region="Forest Navel"
    ),
    "Forest Navel - Gravity Machine": PikminLocationData(
        id=11021,
        region="Forest Navel"
    ),
    
    # Rivage Lointain (The Distant Spring)
    "Distant Spring - First Area": PikminLocationData(
        id=11030,
        region="Distant Spring"
    ),
    "Distant Spring - Libra": PikminLocationData(
        id=11031,
        region="Distant Spring"
    ),
    
    # Événements spéciaux basés sur le nombre de Pikmin
    "Collect 10 Red Pikmin": PikminLocationData(
        id=11100,
        region="Impact Site",
        rule="red_pikmin_count >= 10"
    ),
    "Collect 25 Red Pikmin": PikminLocationData(
        id=11101,
        region="Impact Site", 
        rule="red_pikmin_count >= 25"
    ),
    "Collect 50 Red Pikmin": PikminLocationData(
        id=11102,
        region="Impact Site",
        rule="red_pikmin_count >= 50"
    ),
    "Collect 100 Red Pikmin": PikminLocationData(
        id=11103,
        region="Impact Site",
        rule="red_pikmin_count >= 100"
    ),
    
    # Événements de progression
    "First Day Complete": PikminLocationData(
        id=11200,
        region="Impact Site"
    ),
    "Discover Yellow Pikmin": PikminLocationData(
        id=11201,
        region="Forest of Hope"
    ),
    "Discover Blue Pikmin": PikminLocationData(
        id=11202,
        region="Forest Navel"
    ),
    
    # Boss battles
    "Defeat Armored Cannon Larva": PikminLocationData(
        id=11300,
        region="Impact Site"
    ),
    "Defeat Beady Long Legs": PikminLocationData(
        id=11301,
        region="Forest of Hope"
    ),
    "Defeat Puffstool": PikminLocationData(
        id=11302,
        region="Forest Navel"
    ),
    "Defeat Emperor Bulblax": PikminLocationData(
        id=11303,
        region="Final Trial"
    )
}

# Emplacements par région
locations_by_region = {
    "Impact Site": [
        "Impact Site - First Pellet",
        "Impact Site - Red Pikmin Discovery", 
        "Impact Site - Main Engine",
        "Collect 10 Red Pikmin",
        "Collect 25 Red Pikmin",
        "Collect 50 Red Pikmin",
        "Collect 100 Red Pikmin",
        "First Day Complete",
        "Defeat Armored Cannon Larva"
    ],
    "Forest of Hope": [
        "Forest of Hope - Entrance Pellet",
        "Forest of Hope - Yellow Pikmin Discovery",
        "Forest of Hope - Eternal Fuel Dynamo",
        "Forest of Hope - Whimsical Radar",
        "Discover Yellow Pikmin",
        "Defeat Beady Long Legs"
    ],
    "Forest Navel": [
        "Forest Navel - Blue Pikmin Discovery",
        "Forest Navel - Gravity Machine",
        "Discover Blue Pikmin",
        "Defeat Puffstool"
    ],
    "Distant Spring": [
        "Distant Spring - First Area",
        "Distant Spring - Libra"
    ],
    "Final Trial": [
        "Defeat Emperor Bulblax"
    ]
}