from typing import Callable

from BaseClasses import CollectionState
from .P1Data import (ALL_PARTS, Area)

can_access: dict[Area, Callable[[CollectionState, int], bool]] = {
    "The Impact Site": lambda state, player: True,
    "The Forest of Hope": lambda state, player: state.has_from_list(ALL_PARTS.keys(), player, 1),
    "The Forest Navel": lambda state, player: state.has_from_list(ALL_PARTS.keys(), player, 5),
    "The Distant Spring": lambda state, player: state.has_from_list(ALL_PARTS.keys(), player, 12),
    "The Final Trial": lambda state, player: state.has_from_list(ALL_PARTS.keys(), player, 29),
}

def can_obtain_reds(state: CollectionState, player: int) -> bool:
    return can_access["The Impact Site"](state, player)


def can_obtain_blues(state: CollectionState, player: int) -> bool:
    return can_access["The Forest Navel"](state, player)


def can_obtain_yellows(state: CollectionState, player: int) -> bool:
    return can_access["The Forest of Hope"](state, player)
