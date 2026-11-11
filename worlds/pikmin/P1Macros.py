from typing import Callable

from BaseClasses import CollectionState
from .P1Data import (ALL_PARTS, Area, AREA_UNLOCK_ORDER, AREA_PART_THRESHOLDS, GENERIC_SHIP_PART_ITEM,
                     PROGRESSIVE_AREA_ITEM, area_unlock_item, area_unlock_order,
                     PROGRESSIVE_ONION_ITEM, onion_unlock_item, onion_unlock_order)


def _can_access_area(area: str, state: CollectionState, player: int) -> bool:
    world = state.multiworld.worlds[player]
    if area in world.starting_areas:
        return True
    mode = world.options.shuffle_unlock_areas.value
    if mode == 1:
        return state.has(PROGRESSIVE_AREA_ITEM, player, area_unlock_order(world.starting_areas).index(area) + 1)
    if mode == 2:
        return state.has(area_unlock_item(area), player)
    if area not in AREA_PART_THRESHOLDS:
        return True
    if world.options.goal == 2:
        return state.has(GENERIC_SHIP_PART_ITEM, player, AREA_PART_THRESHOLDS[area])
    return state.has_from_list(ALL_PARTS.keys(), player, AREA_PART_THRESHOLDS[area])


can_access: dict[Area, Callable[[CollectionState, int], bool]] = {
    area: (lambda state, player, area=area: _can_access_area(area, state, player))
    for area in Area.__args__
}

def can_obtain_any(state: CollectionState, player: int) -> bool:
    """At least one Pikmin colour, needed to carry anything."""
    return can_obtain_reds(state, player) or can_obtain_yellows(state, player) \
        or can_obtain_blues(state, player)


def can_obtain_reds(state: CollectionState, player: int) -> bool:
    return _can_obtain("red", "The Impact Site", state, player)


def _has_onion(color: str, state: CollectionState, player: int) -> bool:
    world = state.multiworld.worlds[player]
    if color in world.starting_onions:
        return True
    if world.options.shuffle_unlock_onion == 1:
        order = onion_unlock_order(world.starting_onions)
        return state.has(PROGRESSIVE_ONION_ITEM, player, order.index(color) + 1)
    return state.has(onion_unlock_item(color), player)


def _can_obtain(color: str, area: Area, state: CollectionState, player: int) -> bool:
    world = state.multiworld.worlds[player]
    if world.options.shuffle_unlock_onion:
        return _has_onion(color, state, player)
    return color in world.starting_onions or can_access[area](state, player)


def can_obtain_blues(state: CollectionState, player: int) -> bool:
    return _can_obtain("blue", "The Forest Navel", state, player)


def can_obtain_yellows(state: CollectionState, player: int) -> bool:
    return _can_obtain("yellow", "The Forest of Hope", state, player)
