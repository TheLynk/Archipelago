# pyright: reportMissingImports=false
from typing import TYPE_CHECKING

from BaseClasses import ItemClassification as IC
from Fill import FillError

from .Items import ITEM_TABLE, item_factory

if TYPE_CHECKING:
    from .__init__ import PikminWorld

def generate_itempool(world: "PikminWorld") -> None:
    """
    Generate the item pool for the world.
    :param world: Pikmin game world.
    """
    multiworld = world.multiworld

    # Get the core pool of items.
    pool, precollected_items = get_pool_core(world)

    # Add precollected items to the multiworld's `precollected_items` list.
    for item in precollected_items:
        multiworld.push_precollected(item_factory(item, world))

    # Place a "Victory" item on "Land to the Space" for the spoiler log.
    world.get_location("Land to the Space").place_locked_item(item_factory("Victory", world))

    # Create the pool of the remaining shuffled items.
    items = item_factory(pool, world)
    world.random.shuffle(items)

    multiworld.itempool += items

def get_pool_core(world: "PikminWorld") -> tuple[list[str], list[str]]:
    """
    Get the core pool of items and precollected items for the world.

    :param world: Pikmin game world.
    :return: A tuple of the item pool and precollected items.
    """
    pool: list[str] = []
    precollected_items: list[str] = []

    # Split items into three different pools: progression, useful, and filler.
    progression_pool: list[str] = []
    useful_pool: list[str] = []
    filler_pool: list[str] = []
    for item, data in ITEM_TABLE.items():
        if data.type == "Item":
            adjusted_classification = world.item_classification_overrides.get(item)
            classification = data.classification if adjusted_classification is None else adjusted_classification

            if classification & IC.progression:
                progression_pool.extend([item] * data.quantity)
            elif classification & IC.useful:
                useful_pool.extend([item] * data.quantity)
            else:
                filler_pool.extend([item] * data.quantity)

    # Assign useful and filler items to item pools in the world.
    world.random.shuffle(useful_pool)
    world.random.shuffle(filler_pool)
    world.useful_pool = useful_pool
    world.filler_pool = filler_pool

    # Add filler items to place into excluded locations.
    excluded_locations = world.progress_locations.intersection(world.options.exclude_locations)
    pool.extend([world.get_filler_item_name() for _ in excluded_locations])

    # The remaining of items left to place should be the same as the number of non-excluded locations in the world.
    nonexcluded_locations = [
        location
        for location in world.multiworld.get_locations(world.player)
        if location.name not in world.options.exclude_locations
    ]
    num_items_left_to_place = len(nonexcluded_locations) - 1

    # All progression items are added to the item pool.
    if len(progression_pool) > num_items_left_to_place:
        raise FillError(
            "There are insufficient locations to place progression items! "
            f"Trying to place {len(progression_pool)} items in only {num_items_left_to_place} locations."
        )
    pool.extend(progression_pool)
    num_items_left_to_place -= len(progression_pool)

    # Place useful items, then filler items to fill out the remaining locations.
    pool.extend([world.get_filler_item_name(strict=False) for _ in range(num_items_left_to_place)])

    return pool, precollected_items