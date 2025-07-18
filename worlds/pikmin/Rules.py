from __future__ import annotations
from typing import TYPE_CHECKING
from BaseClasses import CollectionState
from .Items import item_table
from .Locations import location_table
from .names import ItemName, RegionName

if TYPE_CHECKING:
    from . import PikminWorld

def set_rules(world: PikminWorld):
    player = world.player
    multiworld = world.multiworld

    # Basic access rules: having the specific Pikmin type unlocks areas that need it.
    # This is a simplified logic to ensure the world is functional.
    
    # Access to Forest of Hope requires Yellow Pikmin (for bomb rocks)
    multiworld.get_entrance("Go to The Forest of Hope", player).access_rule = lambda state: \
        state.has(ItemName.YELLOW_PIKMIN, player)

    # Access to Forest Navel requires Blue Pikmin (for water)
    multiworld.get_entrance("Go to The Forest Navel", player).access_rule = lambda state: \
        state.has(ItemName.BLUE_PIKMIN, player)

    # Access to Distant Spring requires both Yellow and Blue Pikmin
    multiworld.get_entrance("Go to The Distant Spring", player).access_rule = lambda state: \
        state.has(ItemName.YELLOW_PIKMIN, player) and state.has(ItemName.BLUE_PIKMIN, player)

    # Access to Final Trial requires all Pikmin types
    multiworld.get_entrance("Go to The Final Trial", player).access_rule = lambda state: \
        state.has(ItemName.RED_PIKMIN, player) and \
        state.has(ItemName.YELLOW_PIKMIN, player) and \
        state.has(ItemName.BLUE_PIKMIN, player)

    # Set location rules based on their requirements from the location_table
    for loc_name, loc_data in location_table.items():
        location = multiworld.get_location(loc_name, player)
        if loc_data.requires_pikmin:
            required_pikmin_item = f"{loc_data.requires_pikmin} Discovery"
            location.access_rule = lambda state, item=required_pikmin_item: state.has(item, player)

    # Set the completion condition
    multiworld.completion_condition[player] = lambda state: state.has("Ship Repaired", player)