from collections.abc import Callable
from typing import TYPE_CHECKING

from BaseClasses import MultiWorld
from worlds.AutoWorld import LogicMixin
from worlds.generic.Rules import set_rule, add_rule

if TYPE_CHECKING:
    from . import PikminWorld

class PikminLogic(LogicMixin):
    """
    Logic mixin for Pikmin world rules.
    """

    multiworld: MultiWorld

    def _pikmin_has_red_pikmin(self, player: int) -> bool:
        """Check if player has access to Red Pikmin."""
        return self.has("Unlock Red Pikmin", player)
    
    def _pikmin_has_yellow_pikmin(self, player: int) -> bool:
        """Check if player has access to Yellow Pikmin."""
        return self.has("Unlock Yellow Pikmin", player)
    
    def _pikmin_has_blue_pikmin(self, player: int) -> bool:
        """Check if player has access to Blue Pikmin."""
        return self.has("Unlock Blue Pikmin", player)
    
    def _pikmin_can_access_area(self, area_name: str, player: int) -> bool:
        """Check if player can access a specific area."""
        area_items = {
            "The Impact Site": "The Impact Site",
            "The Forest of Hope": "The Forest Of Hope", 
            "The Forest Navel": "The Forest Navel",
            "The Distant Spring": "The Distant Spring",
            "The Final Trial": "The Final Trial"
        }
        return self.has(area_items.get(area_name, ""), player)
    
    def _pikmin_can_break_walls(self, wall_type: str, player: int) -> bool:
        """Check if player can break specific wall types."""
        if wall_type == "red":
            return self._pikmin_has_red_pikmin(player)
        elif wall_type == "yellow":
            return self._pikmin_has_yellow_pikmin(player)
        elif wall_type == "blue":
            return self._pikmin_has_blue_pikmin(player)
        return False
    
    def _pikmin_can_defeat_boss(self, boss_name: str, player: int) -> bool:
        """Check if player can defeat specific bosses."""
        boss_requirements = {
            "Armored Cannon Beetle": self._pikmin_has_red_pikmin(player),
            "Burrowing Snagret": self._pikmin_has_yellow_pikmin(player),
            "Smoky Progg": self._pikmin_has_blue_pikmin(player),
            "Emperor Bulblax": (self._pikmin_has_red_pikmin(player) and 
                              self._pikmin_has_yellow_pikmin(player) and 
                              self._pikmin_has_blue_pikmin(player))
        }
        return boss_requirements.get(boss_name, False)

def set_rules(world: "PikminWorld") -> None:
    """
    Define the logic rules for locations in Pikmin.
    """
    player = world.player
    multiworld = world.multiworld
    
    # Victory condition - need Main Engine to complete
    multiworld.completion_condition[player] = lambda state: state.has("Main Engine", player)
    
    # Area access rules
    set_rule(multiworld.get_location("Impact Site - Engine", player), 
             lambda state: state._pikmin_can_access_area("The Impact Site", player))
    
    # Forest of Hope access and requirements
    for location_name in ["Forest of Hope - Eternal Fuel Dynamo", "Forest of Hope - Whimsical Radar",
                         "Forest of Hope - Extraordinary Bolt", "Forest of Hope - Nova Blaster",
                         "Forest of Hope - Radiation Canopy"]:
        if location_name in world.location_name_to_id:
            set_rule(multiworld.get_location(location_name, player),
                     lambda state: (state._pikmin_can_access_area("The Forest of Hope", player) and
                                   state._pikmin_has_red_pikmin(player)))
    
    # Red wall requirements
    for location_name in ["Forest of Hope - Red Wall 1", "Forest of Hope - Red Wall 2"]:
        if location_name in world.location_name_to_id:
            set_rule(multiworld.get_location(location_name, player),
                     lambda state: (state._pikmin_can_access_area("The Forest of Hope", player) and
                                   state._pikmin_can_break_walls("red", player)))
    
    # Forest Navel requirements
    for location_name in ["Forest Navel - Geiger Counter", "Forest Navel - Radiation Canopy",
                         "Forest Navel - Bowsprit", "Forest Navel - Gravity Jumper", "Forest Navel - Libra"]:
        if location_name in world.location_name_to_id:
            set_rule(multiworld.get_location(location_name, player),
                     lambda state: (state._pikmin_can_access_area("The Forest Navel", player) and
                                   state._pikmin_has_yellow_pikmin(player)))
    
    # Yellow wall requirements
    if "Forest Navel - Yellow Wall 1" in world.location_name_to_id:
        set_rule(multiworld.get_location("Forest Navel - Yellow Wall 1", player),
                 lambda state: (state._pikmin_can_access_area("The Forest Navel", player) and
                               state._pikmin_can_break_walls("yellow", player)))
    
    # Distant Spring requirements (need Blue Pikmin for water areas)
    for location_name in ["Distant Spring - Chronos Reactor", "Distant Spring - Gluon Drive",
                         "Distant Spring - Zirconium Rotor", "Distant Spring - Repair-type Bolt",
                         "Distant Spring - Pilot's Seat"]:
        if location_name in world.location_name_to_id:
            set_rule(multiworld.get_location(location_name, player),
                     lambda state: (state._pikmin_can_access_area("The Distant Spring", player) and
                                   state._pikmin_has_blue_pikmin(player)))
    
    # Blue wall requirements
    if "Distant Spring - Blue Wall 1" in world.location_name_to_id:
        set_rule(multiworld.get_location("Distant Spring - Blue Wall 1", player),
                 lambda state: (state._pikmin_can_access_area("The Distant Spring", player) and
                               state._pikmin_can_break_walls("blue", player)))
    
    # Final Trial requirements (need all Pikmin types)
    for location_name in ["Final Trial - UV Lamp", "Final Trial - Interstellar Radio",
                         "Final Trial - Bowsprit", "Final Trial - Secret Safe"]:
        if location_name in world.location_name_to_id:
            set_rule(multiworld.get_location(location_name, player),
                     lambda state: (state._pikmin_can_access_area("The Final Trial", player) and
                                   state._pikmin_has_red_pikmin(player) and
                                   state._pikmin_has_yellow_pikmin(player) and
                                   state._pikmin_has_blue_pikmin(player)))
    
    # Boss defeat requirements
    boss_locations = {
        "Forest of Hope - Armored Cannon Beetle Defeated": ("The Forest of Hope", "Armored Cannon Beetle"),
        "Forest Navel - Burrowing Snagret Defeated": ("The Forest Navel", "Burrowing Snagret"), 
        "Distant Spring - Smoky Progg Defeated": ("The Distant Spring", "Smoky Progg"),
        "Final Trial - Emperor Bulblax Defeated": ("The Final Trial", "Emperor Bulblax")
    }
    
    for location_name, (area, boss) in boss_locations.items():
        if location_name in world.location_name_to_id:
            set_rule(multiworld.get_location(location_name, player),
                     lambda state, a=area, b=boss: (state._pikmin_can_access_area(a, player) and
                                                    state._pikmin_can_defeat_boss(b, player)))
    
    # Pikmin number milestones - require appropriate Pikmin type
    red_pikmin_locations = [f"Pikmin Red - {i}" for i in range(10, 101, 10)]
    for location_name in red_pikmin_locations:
        if location_name in world.location_name_to_id:
            set_rule(multiworld.get_location(location_name, player),
                     lambda state: state._pikmin_has_red_pikmin(player))

def set_completion_rules(world: "PikminWorld") -> None:
    """
    Set the completion condition for the world.
    """
    player = world.player
    multiworld = world.multiworld
    
    # Player needs Main Engine to complete (victory item)
    multiworld.completion_condition[player] = lambda state: state.has("Main Engine", player)