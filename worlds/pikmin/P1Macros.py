from typing import Callable

from BaseClasses import CollectionState
from .P1Data import (ALL_PARTS, Area, AREA_UNLOCK_ORDER, AREA_PART_THRESHOLDS,
                     PROGRESSIVE_AREA_ITEM, area_unlock_item,
                     ONION_UNLOCK_ORDER, PROGRESSIVE_ONION_ITEM, onion_unlock_item)


def _can_access_area(area: str, state: CollectionState, player: int) -> bool:
    if area not in AREA_UNLOCK_ORDER:
        return True
    mode = state.multiworld.worlds[player].options.shuffle_unlock_areas.value
    if mode == 1:
        return state.has(PROGRESSIVE_AREA_ITEM, player, AREA_UNLOCK_ORDER.index(area) + 1)
    if mode == 2:
        return state.has(area_unlock_item(area), player)
    return state.has_from_list(ALL_PARTS.keys(), player, AREA_PART_THRESHOLDS[area])


can_access: dict[Area, Callable[[CollectionState, int], bool]] = {
    area: (lambda state, player, area=area: _can_access_area(area, state, player))
    for area in Area.__args__
}

def can_obtain_reds(state: CollectionState, player: int) -> bool:
    return can_access["The Impact Site"](state, player)


def _has_onion(color: str, state: CollectionState, player: int) -> bool:
    mode = state.multiworld.worlds[player].options.shuffle_unlock_onion.value
    if mode == 1:
        return state.has(PROGRESSIVE_ONION_ITEM, player, ONION_UNLOCK_ORDER.index(color) + 1)
    return state.has(onion_unlock_item(color), player)


def can_obtain_blues(state: CollectionState, player: int) -> bool:
    if state.multiworld.worlds[player].options.shuffle_unlock_onion:
        return _has_onion("blue", state, player)
    return can_access["The Forest Navel"](state, player)


def can_obtain_yellows(state: CollectionState, player: int) -> bool:
    if state.multiworld.worlds[player].options.shuffle_unlock_onion:
        return _has_onion("yellow", state, player)
    return can_access["The Forest of Hope"](state, player)
