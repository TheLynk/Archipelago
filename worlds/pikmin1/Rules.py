import typing
from BaseClasses import CollectionState
from worlds.generic.Rules import add_rule

if typing.TYPE_CHECKING:
    from . import Pikmin1World


def has_pikmin_count(state: CollectionState, player: int, count: int) -> bool:
    """Check if player has enough Pikmin seeds to reach the count."""
    red_seeds = state.count("Red Pikmin Seeds", player)
    blue_seeds = state.count("Blue Pikmin Seeds", player)
    yellow_seeds = state.count("Yellow Pikmin Seeds", player)
    
    total_seeds = red_seeds + blue_seeds + yellow_seeds
    return total_seeds >= count


def set_rules(world: "Pikmin1World") -> None:
    """Set rules for the Pikmin 1 world."""
    
    # Rules for Pikmin collection milestones
    # These are automatically handled by the client checking memory
    # But we can add logical dependencies here
    
    # Example: Need some Pikmin seeds to reach higher counts
    add_rule(world.multiworld.get_location("Pikmin Rouge 20", world.player),
             lambda state: has_pikmin_count(state, world.player, 15))
    
    # Ship part rules - example progression
    add_rule(world.multiworld.get_location("Second Ship Part", world.player),
             lambda state: state.has("Main Engine", world.player))
    
    add_rule(world.multiworld.get_location("Third Ship Part", world.player),
             lambda state: state.has("Main Engine", world.player) and 
                          state.has("Positron Generator", world.player))