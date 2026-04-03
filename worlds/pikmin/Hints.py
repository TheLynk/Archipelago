import logging
from typing import TYPE_CHECKING

from BaseClasses import Location, MultiWorld
from .P1Data import ALL_PARTS

if TYPE_CHECKING:
    from . import P1World

logger = logging.getLogger(__name__)

SHIP_PART_HINTS = {
    "Bowsprit": 0,
    "Gluon Drive": 1,
    "Anti-Dioxin Filter": 2,
    "Eternal Fuel Dynamo": 3,
    "Main Engine": 4,
    "Whimsical Radar": 5,
    "Interstellar Radio": 6,
    "Guard Satellite": 7,
    "Chronos Reactor": 8,
    "Radiation Canopy": 9,
    "Geiger Counter": 10,
    "Sagittarius": 11,
    "Libra": 12,
    "Omega Stabilizer": 13,
    "#1 Ionium Jet": 14,
    "#2 Ionium Jet": 15,
    "Shock Absorber": 16,
    "Gravity Jumper": 17,
    "Pilot's Seat": 18,
    "Nova Blaster": 19,
    "Automatic Gear": 20,
    "Zirconium Rotor": 21,
    "Extraordinary Bolt": 22,
    "Repair-Type Bolt": 23,
    "Space Float": 24,
    "Massage Machine": 25,
    "Secret Safe": 26,
    "Positron Generator": 27,
    "Analog Computer": 28,
    "UV Lamp": 29,
}

SHIP_PART_IDS = {data.ap_id for data in ALL_PARTS.values()}


def _get_location_for_item_mode(world: "P1World", player: int, hint_name: str) -> Location | None:
    """
    Mode 1 – "item" hint mode.
    Returns the location that holds the named ship part belonging to `player`,
    searching only among that player's own locations.
    This tells the player *where their own copy* of each part was placed,
    even if it ended up in another player's world.
    """
    for loc in world.multiworld.get_filled_locations(player):
        if loc.item is not None and loc.item.name == hint_name and loc.item.player == player:
            return loc
    return None


def get_hints_by_option(multiworld: MultiWorld, player_hints: set[int]) -> None:
    # Build a lookup index: (item_name, owner_player) -> location
    # Each ship part name exists exactly once per player, so this key is unique.
    # MUST be called from post_fill() — all locations must already be filled.
    ship_part_index: dict[tuple[str, int], Location] = {}
    filled_count = 0
    for loc in multiworld.get_filled_locations():
        filled_count += 1
        item = loc.item
        if item is not None and item.name in SHIP_PART_HINTS:
            key = (item.name, item.player)
            # Keep only the first occurrence (should be unique per key)
            if key not in ship_part_index:
                ship_part_index[key] = loc

    logger.debug(f"[Hints] Built index from {filled_count} filled locations, "
                 f"{len(ship_part_index)} ship part entries")

    player_hint_worlds = sorted(player_hints)

    for player_int in player_hint_worlds:
        world: "P1World" = multiworld.worlds[player_int]

        if world.options.ship_part_hint_mode.value == 0:
            continue

        hint_mode = world.options.ship_part_hint_mode.value

        for hint_name in SHIP_PART_HINTS.keys():
            if hint_mode == 1:
                loc: Location = _get_location_for_item_mode(world, player_int, hint_name)
            else:
                loc: Location = ship_part_index.get((hint_name, player_int))

            if loc is None:
                logger.warning(f"[Hints] No location found for ({hint_name}, player={player_int}) "
                               f"— was get_hints_by_option called from post_fill()?")
                continue

            # Safety check: the item at this location must belong to player_int
            if hint_mode == 2 and loc.item.player != player_int:
                logger.error(f"[Hints] BUG: location {loc.name} has item owned by player "
                             f"{loc.item.player}, expected player {player_int}")
                continue

            if loc.item.advancement:
                icolor = "Prog"
            elif loc.item.trap:
                icolor = "Trap"
            else:
                icolor = "Other"

            hint = {hint_name: {
                "Item": loc.item.name,
                "Location": loc.name,
                "Location ID": str(loc.address),
                "Rec Player": multiworld.player_name[loc.item.player],
                "Send Player": multiworld.player_name[loc.player],
                "Send Player ID": str(loc.player),
                "Game": loc.game,
                "Class": icolor,
                "Hint Mode": hint_mode,
            }}

            world.hints.update(hint)