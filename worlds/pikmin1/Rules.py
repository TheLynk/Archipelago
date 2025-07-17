"""
Règles de logique pour Pikmin 1 GameCube PAL
"""

from typing import TYPE_CHECKING
from BaseClasses import CollectionState

if TYPE_CHECKING:
    from . import PikminWorld


def set_rules(world: "PikminWorld") -> None:
    """Définir les règles de logique pour le monde Pikmin"""
    
    # Règles pour l'accès aux régions
    set_region_rules(world)
    
    # Règles pour les locations spécifiques
    set_location_rules(world)


def set_region_rules(world: "PikminWorld") -> None:
    """Règles d'accès aux régions"""
    
    # Pour l'instant, toutes les régions sont accessibles depuis le début
    # Peut être modifié pour nécessiter certains items
    pass


def set_location_rules(world: "PikminWorld") -> None:
    """Règles d'accès aux locations"""
    
    multiworld = world.multiworld
    player = world.player
    
    # Règle pour la location "10 Red Pikmin"
    # Cette location sera déclenchée par la lecture mémoire
    multiworld.get_location("10 Red Pikmin", player).access_rule = lambda state: True
    
    # Règles pour les autres locations
    multiworld.get_location("First Pellet", player).access_rule = lambda state: True
    
    # Les découvertes de Pikmin nécessitent d'être dans la bonne région
    multiworld.get_location("Yellow Pikmin Discovery", player).access_rule = \
        lambda state: state.can_reach("The Forest of Hope", "Region", player)
    
    multiworld.get_location("Blue Pikmin Discovery", player).access_rule = \
        lambda state: state.can_reach("The Forest Navel", "Region", player)


def has_red_pikmin(state: CollectionState, player: int) -> bool:
    """Vérifier si le joueur a des pikmin rouge"""
    return state.has("Red Pikmin Sprout", player)


def has_yellow_pikmin(state: CollectionState, player: int) -> bool:
    """Vérifier si le joueur a des pikmin jaunes"""
    return state.has("Yellow Pikmin Sprout", player)


def has_blue_pikmin(state: CollectionState, player: int) -> bool:
    """Vérifier si le joueur a des pikmin bleus"""
    return state.has("Blue Pikmin Sprout", player)