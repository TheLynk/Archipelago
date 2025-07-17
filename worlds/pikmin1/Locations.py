"""
Locations pour Pikmin 1 GameCube PAL
"""

from typing import Dict, NamedTuple, Optional
from BaseClasses import Location


class LocationData(NamedTuple):
    code: Optional[int]
    region: str


class PikminLocation(Location):
    game: str = "Pikmin"


# Base location code - doit être unique par monde
base_id = 0x1000000  # Même base que les items mais différent range


location_table: Dict[str, LocationData] = {
    # Location principale pour le test des 10 pikmin rouge
    "10 Red Pikmin": LocationData(base_id + 1, "The Impact Site"),
    
    # Autres locations d'exemple
    "First Pellet": LocationData(base_id + 2, "The Impact Site"),
    "Yellow Pikmin Discovery": LocationData(base_id + 3, "The Forest of Hope"),
    "Blue Pikmin Discovery": LocationData(base_id + 4, "The Forest Navel"),
    "Pellet Posy 1": LocationData(base_id + 5, "The Impact Site"),
    "Pellet Posy 2": LocationData(base_id + 6, "The Forest of Hope"),
    "Nectar Drop": LocationData(base_id + 7, "The Impact Site"),
    "Ship Part 1": LocationData(base_id + 8, "The Impact Site"),
    "Ship Part 2": LocationData(base_id + 9, "The Forest of Hope"),
    "Ship Part 3": LocationData(base_id + 10, "The Forest Navel"),
}


# Créer le dictionnaire nom -> ID
location_name_to_id: Dict[str, int] = {name: data.code for name, data in location_table.items() if data.code is not None}


def get_location_by_name(name: str) -> LocationData:
    """Obtenir les données d'une location par son nom"""
    return location_table[name]