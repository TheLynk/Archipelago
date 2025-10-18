from dataclasses import dataclass
from Options import DefaultOnToggle, Toggle, Range, PerGameCommonOptions


class EnablePikminLocations(Toggle):
    """Enable generation of locations based on Pikmin collection thresholds"""
    display_name = "Enable Pikmin Collection Locations"
    default = False


class RedPikminLocationsEnabled(Toggle):
    """Enable Red Pikmin collection locations (no ship part requirements)"""
    display_name = "Red Pikmin Locations"
    default = True


class RedPikminInterval(Range):
    """Pikmin count interval for Red locations (e.g., 12 = 12, 24, 36... locations)"""
    display_name = "Red Pikmin Interval"
    range_start = 1
    range_end = 100
    default = 5


class YellowPikminLocationsEnabled(Toggle):
    """Enable Yellow Pikmin collection locations (requires 1 ship part)"""
    display_name = "Yellow Pikmin Locations"
    default = True


class YellowPikminInterval(Range):
    """Pikmin count interval for Yellow locations"""
    display_name = "Yellow Pikmin Interval"
    range_start = 1
    range_end = 100
    default = 5


class BluePikminLocationsEnabled(Toggle):
    """Enable Blue Pikmin collection locations (requires 5 ship parts)"""
    display_name = "Blue Pikmin Locations"
    default = True


class BluePikminInterval(Range):
    """Pikmin count interval for Blue locations"""
    display_name = "Blue Pikmin Interval"
    range_start = 1
    range_end = 100
    default = 5


class FirstPartIsLocal(DefaultOnToggle):
    """
    Force collecting the Main Engine to give a ship part.
    This can be useful to prevent getting stuck immediately at the start of the game.
    """
    display_name = "Local First Part"


class LastPartIsLocal(DefaultOnToggle):
    """
    Force collecting the Secret Safe to give a ship part.
    Since you complete Pikmin 1 by collecting the last ship part, it could be give a required item for another player.
    This option prevents this, so other players won't ever need to wait for Pikmin to finish.
    """
    display_name = "Local Last Part"


@dataclass
class P1Options(PerGameCommonOptions):
    enable_pikmin_locations: EnablePikminLocations
    red_pikmin_locations_enabled: RedPikminLocationsEnabled
    red_pikmin_interval: RedPikminInterval
    yellow_pikmin_locations_enabled: YellowPikminLocationsEnabled
    yellow_pikmin_interval: YellowPikminInterval
    blue_pikmin_locations_enabled: BluePikminLocationsEnabled
    blue_pikmin_interval: BluePikminInterval
    first_part_is_local: FirstPartIsLocal
    last_part_is_local: LastPartIsLocal