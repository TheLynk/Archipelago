from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import CollectionState
from .items import PikminItem, get_item_by_name
from .locations import PikminLocation
from .names import ItemName, LocationName, RegionName

if TYPE_CHECKING:
    from . import PikminWorld


def has_pikmin_type(state: CollectionState, player: int, pikmin_type: str) -> bool:
    """Check if player has a specific Pikmin type."""
    return state.has(pikmin_type, player)


def has_pikmin_count(state: CollectionState, player: int, count: int) -> bool:
    """Check if player has at least a certain number of Pikmin."""
    total_pikmin = 0
    pikmin_types = [
        ItemName.RED_PIKMIN,
        ItemName.BLUE_PIKMIN,
        ItemName.YELLOW_PIKMIN,
        ItemName.WHITE_PIKMIN,
        ItemName.PURPLE_PIKMIN,
        ItemName.ROCK_PIKMIN,
        ItemName.WINGED_PIKMIN,
        ItemName.ICE_PIKMIN,
        ItemName.GLOW_PIKMIN
    ]
    
    for pikmin_type in pikmin_types:
        if state.has(pikmin_type, player):
            total_pikmin += state.count(pikmin_type, player)
    
    return total_pikmin >= count


def has_captain_ability(state: CollectionState, player: int, ability: str) -> bool:
    """Check if player has a specific captain ability."""
    return state.has(ability, player)


def has_ship_part(state: CollectionState, player: int, part: str) -> bool:
    """Check if player has a specific ship part."""
    return state.has(part, player)


def has_treasure(state: CollectionState, player: int, treasure: str) -> bool:
    """Check if player has a specific treasure."""
    return state.has(treasure, player)


def has_upgrade(state: CollectionState, player: int, upgrade: str) -> bool:
    """Check if player has a specific upgrade."""
    return state.has(upgrade, player)


def can_break_wall(state: CollectionState, player: int, wall_type: str) -> bool:
    """Check if player can break a specific type of wall."""
    if wall_type == "crystal":
        return has_pikmin_type(state, player, ItemName.ROCK_PIKMIN)
    elif wall_type == "dirt":
        return has_pikmin_count(state, player, 10)  # Any Pikmin can break dirt walls
    elif wall_type == "electric":
        return has_pikmin_type(state, player, ItemName.YELLOW_PIKMIN)
    elif wall_type == "fire":
        return has_pikmin_type(state, player, ItemName.RED_PIKMIN)
    elif wall_type == "water":
        return has_pikmin_type(state, player, ItemName.BLUE_PIKMIN)
    elif wall_type == "ice":
        return has_pikmin_type(state, player, ItemName.ICE_PIKMIN) or has_pikmin_type(state, player, ItemName.RED_PIKMIN)
    else:
        return True


def can_defeat_enemy(state: CollectionState, player: int, enemy_type: str) -> bool:
    """Check if player can defeat a specific enemy type."""
    if enemy_type == "fiery":
        return has_pikmin_type(state, player, ItemName.RED_PIKMIN)
    elif enemy_type == "watery":
        return has_pikmin_type(state, player, ItemName.BLUE_PIKMIN)
    elif enemy_type == "electric":
        return has_pikmin_type(state, player, ItemName.YELLOW_PIKMIN)
    elif enemy_type == "poisonous":
        return has_pikmin_type(state, player, ItemName.WHITE_PIKMIN)
    elif enemy_type == "aerial":
        return has_pikmin_type(state, player, ItemName.WINGED_PIKMIN) or has_pikmin_type(state, player, ItemName.YELLOW_PIKMIN)
    elif enemy_type == "armored":
        return has_pikmin_type(state, player, ItemName.ROCK_PIKMIN)
    elif enemy_type == "heavy":
        return has_pikmin_type(state, player, ItemName.PURPLE_PIKMIN) or has_pikmin_count(state, player, 20)
    elif enemy_type == "frozen":
        return has_pikmin_type(state, player, ItemName.ICE_PIKMIN) or has_pikmin_type(state, player, ItemName.RED_PIKMIN)
    else:
        return has_pikmin_count(state, player, 5)  # Basic enemies


def can_access_area(state: CollectionState, player: int, area: str) -> bool:
    """Check if player can access a specific area."""
    if area == RegionName.FOREST_OF_HOPE:
        return has_pikmin_type(state, player, ItemName.RED_PIKMIN)
    elif area == RegionName.FOREST_NAVEL:
        return (has_pikmin_type(state, player, ItemName.YELLOW_PIKMIN) and
                has_pikmin_type(state, player, ItemName.BLUE_PIKMIN))
    elif area == RegionName.DISTANT_SPRING:
        return (has_pikmin_type(state, player, ItemName.BLUE_PIKMIN) and
                has_pikmin_count(state, player, 15))
    elif area == RegionName.FINAL_TRIAL:
        return (has_pikmin_type(state, player, ItemName.RED_PIKMIN) and
                has_pikmin_type(state, player, ItemName.BLUE_PIKMIN) and
                has_pikmin_type(state, player, ItemName.YELLOW_PIKMIN) and
                has_pikmin_count(state, player, 30))
    elif area == RegionName.VALLEY_OF_REPOSE:
        return has_pikmin_type(state, player, ItemName.RED_PIKMIN)
    elif area == RegionName.AWAKENING_WOOD:
        return (has_pikmin_type(state, player, ItemName.BLUE_PIKMIN) and
                has_pikmin_type(state, player, ItemName.YELLOW_PIKMIN))
    elif area == RegionName.PERPLEXING_POOL:
        return (has_pikmin_type(state, player, ItemName.BLUE_PIKMIN) and
                has_pikmin_type(state, player, ItemName.WHITE_PIKMIN))
    elif area == RegionName.WISTFUL_WILD:
        return (has_pikmin_type(state, player, ItemName.PURPLE_PIKMIN) and
                has_pikmin_type(state, player, ItemName.WHITE_PIKMIN) and
                has_pikmin_count(state, player, 40))
    elif area == RegionName.TROPICAL_WILDS:
        return has_pikmin_type(state, player, ItemName.ROCK_PIKMIN)
    elif area == RegionName.GARDEN_OF_HOPE:
        return (has_pikmin_type(state, player, ItemName.ROCK_PIKMIN) and
                has_pikmin_type(state, player, ItemName.BLUE_PIKMIN))
    elif area == RegionName.DISTANT_TUNDRA:
        return (has_pikmin_type(state, player, ItemName.WINGED_PIKMIN) and
                has_pikmin_type(state, player, ItemName.YELLOW_PIKMIN))
    elif area == RegionName.TWILIGHT_RIVER:
        return (has_pikmin_type(state, player, ItemName.WINGED_PIKMIN) and
                has_pikmin_type(state, player, ItemName.BLUE_PIKMIN) and
                has_pikmin_count(state, player, 25))
    elif area == RegionName.FORMIDABLE_OAK:
        return (has_pikmin_type(state, player, ItemName.ROCK_PIKMIN) and
                has_pikmin_type(state, player, ItemName.WINGED_PIKMIN) and
                has_pikmin_type(state, player, ItemName.BLUE_PIKMIN) and
                has_pikmin_type(state, player, ItemName.YELLOW_PIKMIN) and
                has_pikmin_count(state, player, 50))
    else:
        return True


def can_complete_cave(state: CollectionState, player: int, cave: str) -> bool:
    """Check if player can complete a specific cave."""
    if cave == "Emergence_Cave":
        return has_pikmin_type(state, player, ItemName.RED_PIKMIN)
    elif cave == "Subterranean_Complex":
        return (has_pikmin_type(state, player, ItemName.PURPLE_PIKMIN) and
                has_pikmin_count(state, player, 20))
    elif cave == "Frontier_Cavern":
        return (has_pikmin_type(state, player, ItemName.WHITE_PIKMIN) and
                has_pikmin_type(state, player, ItemName.PURPLE_PIKMIN))
    elif cave == "Hole_of_Beasts":
        return (has_pikmin_type(state, player, ItemName.RED_PIKMIN) and
                has_pikmin_count(state, player, 15))
    elif cave == "White_Flower_Garden":
        return has_pikmin_type(state, player, ItemName.WHITE_PIKMIN)
    elif cave == "Bulblax_Kingdom":
        return (has_pikmin_type(state, player, ItemName.PURPLE_PIKMIN) and
                has_pikmin_type(state, player, ItemName.RED_PIKMIN) and
                has_pikmin_count(state, player, 30))
    elif cave == "Snagret_Hole":
        return (has_pikmin_type(state, player, ItemName.YELLOW_PIKMIN) and
                has_pikmin_count(state, player, 25))
    elif cave == "Citadel_of_Spiders":
        return (has_pikmin_type(state, player, ItemName.WHITE_PIKMIN) and
                has_pikmin_type(state, player, ItemName.PURPLE_PIKMIN) and
                has_pikmin_count(state, player, 35))
    elif cave == "Gluttons_Kitchen":
        return (has_pikmin_type(state, player, ItemName.BLUE_PIKMIN) and
                has_pikmin_type(state, player, ItemName.RED_PIKMIN) and
                has_pikmin_count(state, player, 30))
    elif cave == "Shower_Room":
        return (has_pikmin_type(state, player, ItemName.BLUE_PIKMIN) and
                has_pikmin_type(state, player, ItemName.WHITE_PIKMIN))
    elif cave == "Submerged_Castle":
        return (has_pikmin_type(state, player, ItemName.BLUE_PIKMIN) and
                has_pikmin_count(state, player, 40))
    elif cave == "Cavern_of_Chaos":
        return (has_pikmin_type(state, player, ItemName.PURPLE_PIKMIN) and
                has_pikmin_type(state, player, ItemName.WHITE_PIKMIN) and
                has_pikmin_count(state, player, 45))
    elif cave == "Hole_of_Heroes":
        return (has_pikmin_type(state, player, ItemName.RED_PIKMIN) and
                has_pikmin_type(state, player, ItemName.BLUE_PIKMIN) and
                has_pikmin_type(state, player, ItemName.YELLOW_PIKMIN) and
                has_pikmin_type(state, player, ItemName.WHITE_PIKMIN) and
                has_pikmin_type(state, player, ItemName.PURPLE_PIKMIN) and
                has_pikmin_count(state, player, 50))
    elif cave == "Dream_Den":
        return (has_pikmin_type(state, player, ItemName.RED_PIKMIN) and
                has_pikmin_type(state, player, ItemName.BLUE_PIKMIN) and
                has_pikmin_type(state, player, ItemName.YELLOW_PIKMIN) and
                has_pikmin_type(state, player, ItemName.WHITE_PIKMIN) and
                has_pikmin_type(state, player, ItemName.PURPLE_PIKMIN) and
                has_pikmin_count(state, player, 60))
    else:
        return True


def can_carry_pellet(state: CollectionState, player: int, pellet_weight: int) -> bool:
    """Check if player can carry a pellet of specific weight."""
    return has_pikmin_count(state, player, pellet_weight)


def can_build_bridge(state: CollectionState, player: int, bridge_type: str) -> bool:
    """Check if player can build a specific type of bridge."""
    if bridge_type == "stick":
        return has_pikmin_count(state, player, 30)
    elif bridge_type == "clay":
        return has_pikmin_count(state, player, 20)
    elif bridge_type == "fragment":
        return has_pikmin_count(state, player, 25)
    else:
        return has_pikmin_count(state, player, 15)


def can_use_captain_ability(state: CollectionState, player: int, ability: str) -> bool:
    """Check if player can use a specific captain ability."""
    if ability == "whistle":
        return True  # Always available
    elif ability == "throw":
        return has_pikmin_count(state, player, 1)
    elif ability == "punch":
        return has_captain_ability(state, player, ItemName.ROCKET_FIST)
    elif ability == "charge":
        return has_captain_ability(state, player, ItemName.RUSH_BOOTS)
    elif ability == "spray":
        return (has_upgrade(state, player, ItemName.ULTRA_SPICY_SPRAY) or
                has_upgrade(state, player, ItemName.ULTRA_BITTER_SPRAY))
    else:
        return True


def set_rules(world: PikminWorld) -> None:
    """Set the rules for the Pikmin world."""
    player = world.player
    multiworld = world.multiworld
    
    # Set entrance rules for different areas
    for entrance in multiworld.get_entrances(player):
        if entrance.name == "Forest of Hope":
            entrance.access_rule = lambda state: can_access_area(state, player, RegionName.FOREST_OF_HOPE)
        elif entrance.name == "Forest Navel":
            entrance.access_rule = lambda state: can_access_area(state, player, RegionName.FOREST_NAVEL)
        elif entrance.name == "Distant Spring":
            entrance.access_rule = lambda state: can_access_area(state, player, RegionName.DISTANT_SPRING)
        elif entrance.name == "Final Trial":
            entrance.access_rule = lambda state: can_access_area(state, player, RegionName.FINAL_TRIAL)
        elif entrance.name == "Valley of Repose":
            entrance.access_rule = lambda state: can_access_area(state, player, RegionName.VALLEY_OF_REPOSE)
        elif entrance.name == "Awakening Wood":
            entrance.access_rule = lambda state: can_access_area(state, player, RegionName.AWAKENING_WOOD)
        elif entrance.name == "Perplexing Pool":
            entrance.access_rule = lambda state: can_access_area(state, player, RegionName.PERPLEXING_POOL)
        elif entrance.name == "Wistful Wild":
            entrance.access_rule = lambda state: can_access_area(state, player, RegionName.WISTFUL_WILD)
        elif entrance.name == "Tropical Wilds":
            entrance.access_rule = lambda state: can_access_area(state, player, RegionName.TROPICAL_WILDS)
        elif entrance.name == "Garden of Hope":
            entrance.access_rule = lambda state: can_access_area(state, player, RegionName.GARDEN_OF_HOPE)
        elif entrance.name == "Distant Tundra":
            entrance.access_rule = lambda state: can_access_area(state, player, RegionName.DISTANT_TUNDRA)
        elif entrance.name == "Twilight River":
            entrance.access_rule = lambda state: can_access_area(state, player, RegionName.TWILIGHT_RIVER)
        elif entrance.name == "Formidable Oak":
            entrance.access_rule = lambda state: can_access_area(state, player, RegionName.FORMIDABLE_OAK)
    
    # Set location rules
    for location in multiworld.get_locations(player):
        if location.name.endswith("Ship Part"):
            # Ship parts generally require specific Pikmin types and counts
            if "Main Engine" in location.name:
                location.access_rule = lambda state: (
                    has_pikmin_type(state, player, ItemName.RED_PIKMIN) and
                    has_pikmin_count(state, player, 30)
                )
            elif "Eternal Fuel Dynamo" in location.name:
                location.access_rule = lambda state: (
                    has_pikmin_type(state, player, ItemName.YELLOW_PIKMIN) and
                    can_defeat_enemy(state, player, "electric")
                )
            elif "Positron Generator" in location.name:
                location.access_rule = lambda state: (
                    has_pikmin_type(state, player, ItemName.BLUE_PIKMIN) and
                    can_defeat_enemy(state, player, "watery")
                )
        
        elif location.name.endswith("Treasure"):
            # Treasures in caves require cave completion
            if "Emergence Cave" in location.name:
                location.access_rule = lambda state: can_complete_cave(state, player, "Emergence_Cave")
            elif "Subterranean Complex" in location.name:
                location.access_rule = lambda state: can_complete_cave(state, player, "Subterranean_Complex")
            elif "Frontier Cavern" in location.name:
                location.access_rule = lambda state: can_complete_cave(state, player, "Frontier_Cavern")
            elif "Hole of Beasts" in location.name:
                location.access_rule = lambda state: can_complete_cave(state, player, "Hole_of_Beasts")
            elif "White Flower Garden" in location.name:
                location.access_rule = lambda state: can_complete_cave(state, player, "White_Flower_Garden")
            elif "Bulblax Kingdom" in location.name:
                location.access_rule = lambda state: can_complete_cave(state, player, "Bulblax_Kingdom")
            elif "Snagret Hole" in location.name:
                location.access_rule = lambda state: can_complete_cave(state, player, "Snagret_Hole")
            elif "Citadel of Spiders" in location.name:
                location.access_rule = lambda state: can_complete_cave(state, player, "Citadel_of_Spiders")
            elif "Gluttons Kitchen" in location.name:
                location.access_rule = lambda state: can_complete_cave(state, player, "Gluttons_Kitchen")
            elif "Shower Room" in location.name:
                location.access_rule = lambda state: can_complete_cave(state, player, "Shower_Room")
            elif "Submerged Castle" in location.name:
                location.access_rule = lambda state: can_complete_cave(state, player, "Submerged_Castle")
            elif "Cavern of Chaos" in location.name:
                location.access_rule = lambda state: can_complete_cave(state, player, "Cavern_of_Chaos")
            elif "Hole of Heroes" in location.name:
                location.access_rule = lambda state: can_complete_cave(state, player, "Hole_of_Heroes")
            elif "Dream Den" in location.name:
                location.access_rule = lambda state: can_complete_cave(state, player, "Dream_Den")
        
        elif location.name.endswith("Fruit"):
            # Fruits in Pikmin 3 require specific combinations
            if "Sunseed Berry" in location.name:
                location.access_rule = lambda state: (
                    has_pikmin_type(state, player, ItemName.RED_PIKMIN) and
                    has_pikmin_count(state, player, 10)
                )
            elif "Heroine's Tear" in location.name:
                location.access_rule = lambda state: (
                    has_pikmin_type(state, player, ItemName.ROCK_PIKMIN) and
                    can_break_wall(state, player, "crystal")
                )
            elif "Zest Bomb" in location.name:
                location.access_rule = lambda state: (
                    has_pikmin_type(state, player, ItemName.WINGED_PIKMIN) and
                    has_pikmin_count(state, player, 15)
                )
        
        elif "Bridge" in location.name:
            # Bridges require specific Pikmin counts
            if "Stick Bridge" in location.name:
                location.access_rule = lambda state: can_build_bridge(state, player, "stick")
            elif "Clay Bridge" in location.name:
                location.access_rule = lambda state: can_build_bridge(state, player, "clay")
            elif "Fragment Bridge" in location.name:
                location.access_rule = lambda state: can_build_bridge(state, player, "fragment")
        
        elif "Wall" in location.name:
            # Walls require specific Pikmin types
            if "Crystal Wall" in location.name:
                location.access_rule = lambda state: can_break_wall(state, player, "crystal")
            elif "Electric Wall" in location.name:
                location.access_rule = lambda state: can_break_wall(state, player, "electric")
            elif "Fire Wall" in location.name:
                location.access_rule = lambda state: can_break_wall(state, player, "fire")
            elif "Water Wall" in location.name:
                location.access_rule = lambda state: can_break_wall(state, player, "water")
            elif "Ice Wall" in location.name:
                location.access_rule = lambda state: can_break_wall(state, player, "ice")
    
    # Set completion condition
    multiworld.completion_condition[player] = lambda state: (
        has_pikmin_type(state, player, ItemName.RED_PIKMIN) and
        has_pikmin_type(state, player, ItemName.BLUE_PIKMIN) and
        has_pikmin_type(state, player, ItemName.YELLOW_PIKMIN) and
        has_pikmin_count(state, player, 100) and
        state.can_reach("Final Trial", "Region", player)
    )