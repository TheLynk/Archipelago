# pyright: reportMissingImports=false
from collections.abc import Callable
from typing import TYPE_CHECKING

from BaseClasses import MultiWorld
from worlds.AutoWorld import LogicMixin
from worlds.generic.Rules import set_rule

if TYPE_CHECKING:
    from . import PikminWorld

class PikminLogic(LogicMixin):
    """
    This class implements some of the game logic for Pikmin.

    This class's methods reference the world's options. All methods defined in this class should be prefixed with
    "_pikmin."
    """

    multiworld: MultiWorld

def set_rules(world: "PikminWorld") -> None:  
    """
    Define the logic rules for locations in Pikmin.
    Rules are only set for locations if they are present in the world.

    :param world: Pikmin game world.
    """

    player = world.player

    world.multiworld.completion_condition[player] = lambda state: state.has("Victory", player)