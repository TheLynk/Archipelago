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

def set_rules(world: "PikminWorld") -> None:
    """
    Define the logic rules for locations in Pikmin.
    """
    player = world.player
    multiworld = world.multiworld
    
    # Victory condition - need Main Engine to complete
    multiworld.completion_condition[player] = lambda state: state.has("Main Engine", player)
    
    # Impact Site locations
    impact_locations = [
        "Impact Site - Main Engine",
        "Impact Site - Positron Generator"
    ]
    
    for location_name in impact_locations:
        if location_name in world.location_name_to_id:
            set_rule(multiworld.get_location(location_name, player), 
                     lambda state: state._pikmin_can_access_area("The Impact Site", player))
    
    # Forest of Hope locations - need Red Pikmin
    forest_hope_locations = [
        "Forest of Hope - Eternal Fuel Dynamo",
        "Forest of Hope - Extraordinary Bolt", 
        "Forest of Hope - Whimsical Radar",
        "Forest of Hope - Radiation Canopy",
        "Forest of Hope - Sagittarius",
        "Forest of Hope - Shock Absorber",
        "Forest of Hope - Nova Blaster"
    ]
    
    for location_name in forest_hope_locations:
        if location_name in world.location_name_to_id:
            set_rule(multiworld.get_location(location_name, player),
                     lambda state: (state._pikmin_can_access_area("The Forest of Hope", player) and
                                   state._pikmin_has_red_pikmin(player)))
    
    # Forest Navel locations - need Yellow Pikmin
    forest_navel_locations = [
        "Forest Navel - Geiger Counter",
        "Forest Navel - Automatic Gear",
        "Forest Navel - #1 Ionium Jet", 
        "Forest Navel - Anti-Dioxin Filter",
        "Forest Navel - Omega Stabilizer",
        "Forest Navel - Gravity Jumper",
        "Forest Navel - Analog Computer",
        "Forest Navel - Guard Satellite",
        "Forest Navel - Libra",
        "Forest Navel - Space Float"
    ]
    
    for location_name in forest_navel_locations:
        if location_name in world.location_name_to_id:
            set_rule(multiworld.get_location(location_name, player),
                     lambda state: (state._pikmin_can_access_area("The Forest Navel", player) and
                                   state._pikmin_has_yellow_pikmin(player)))
    
    # Distant Spring locations - need Blue Pikmin for water areas
    distant_spring_locations = [
        "Distant Spring - Repair-type Bolt",
        "Distant Spring - Gluon Drive",
        "Distant Spring - Zirconium Rotor", 
        "Distant Spring - Interstellar Radio",
        "Distant Spring - Pilot's Seat",
        "Distant Spring - #2 Ionium Jet",
        "Distant Spring - Bowsprit",
        "Distant Spring - Chronos Reactor",
        "Distant Spring - Massage Machine",
        "Distant Spring - UV Lamp"
    ]
    
    for location_name in distant_spring_locations:
        if location_name in world.location_name_to_id:
            set_rule(multiworld.get_location(location_name, player),
                     lambda state: (state._pikmin_can_access_area("The Distant Spring", player) and
                                   state._pikmin_has_blue_pikmin(player)))
    
    # Final Trial locations - need all Pikmin types
    final_trial_locations = [
        "Final Trial - Secret Safe"
    ]
    
    for location_name in final_trial_locations:
        if location_name in world.location_name_to_id:
            set_rule(multiworld.get_location(location_name, player),
                     lambda state: (state._pikmin_can_access_area("The Final Trial", player) and
                                   state._pikmin_has_red_pikmin(player) and
                                   state._pikmin_has_yellow_pikmin(player) and
                                   state._pikmin_has_blue_pikmin(player)))
    
    # Pikmin number milestones - require appropriate Pikmin type
    red_pikmin_locations = [f"Pikmin Red - {i}" for i in range(10, 101, 10)]
    for location_name in red_pikmin_locations:
        if location_name in world.location_name_to_id:
            set_rule(multiworld.get_location(location_name, player),
                     lambda state: state._pikmin_has_red_pikmin(player))
    
    yellow_pikmin_locations = [f"Pikmin Yellow - {i}" for i in range(10, 101, 10)]
    for location_name in yellow_pikmin_locations:
        if location_name in world.location_name_to_id:
            set_rule(multiworld.get_location(location_name, player),
                     lambda state: state._pikmin_has_yellow_pikmin(player))
    
    blue_pikmin_locations = [f"Pikmin Blue - {i}" for i in range(10, 101, 10)]
    for location_name in blue_pikmin_locations:
        if location_name in world.location_name_to_id:
            set_rule(multiworld.get_location(location_name, player),
                     lambda state: state._pikmin_has_blue_pikmin(player))

def set_completion_rules(world: "PikminWorld") -> None:
    """
    Set the completion condition for the world.
    """
    player = world.player
    multiworld = world.multiworld
    
    # Player needs Main Engine to complete (victory item)
    multiworld.completion_condition[player] = lambda state: state.has("Main Engine", player)