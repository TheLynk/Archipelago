"""
Regions pour Pikmin 1 GameCube PAL
"""

from typing import Dict, List, NamedTuple, Optional, TYPE_CHECKING
from BaseClasses import Entrance, Region
from .Locations import PikminLocation, location_table

if TYPE_CHECKING:
    from . import PikminWorld


def create_regions(world: "PikminWorld") -> None:
    """Créer toutes les régions du monde Pikmin"""
    
    # Menu principal (point d'entrée)
    menu = Region("Menu", world.player, world.multiworld)
    world.multiworld.regions.append(menu)
    
    # Région principale - The Impact Site
    impact_site = Region("The Impact Site", world.player, world.multiworld)
    world.multiworld.regions.append(impact_site)
    
    # Autres régions
    forest_hope = Region("The Forest of Hope", world.player, world.multiworld)
    world.multiworld.regions.append(forest_hope)
    
    forest_navel = Region("The Forest Navel", world.player, world.multiworld)
    world.multiworld.regions.append(forest_navel)
    
    # Créer les entrances
    menu.connect(impact_site, "Start Game")
    impact_site.connect(forest_hope, "To Forest of Hope")
    impact_site.connect(forest_navel, "To Forest Navel")
    
    # Ajouter les locations aux régions
    add_locations_to_regions(world)


def add_locations_to_regions(world: "PikminWorld") -> None:
    """Ajouter les locations aux régions appropriées"""
    
    # Organiser les locations par région
    regions = {
        "The Impact Site": [],
        "The Forest of Hope": [],
        "The Forest Navel": [],
    }
    
    # Distribuer les locations
    for location_name, location_data in location_table.items():
        if location_data.region in regions:
            regions[location_data.region].append(location_name)
    
    # Créer les objets Location et les ajouter aux régions
    for region_name, location_names in regions.items():
        region = world.multiworld.get_region(region_name, world.player)
        
        for location_name in location_names:
            location_data = location_table[location_name]
            location = PikminLocation(world.player, location_name, location_data.code, region)
            region.locations.append(location)