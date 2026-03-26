from dataclasses import dataclass
from Options import DefaultOnToggle, Toggle, Range, Choice, PerGameCommonOptions


# ====================================================================
# SHIP PART
# ====================================================================
class FirstPartIsLocal(DefaultOnToggle):
    """
    Force collecting the Main Engine to give a ship part.
    This can be useful to prevent getting stuck immediately at the start of the game.
    """
    display_name = "Local First Part"


class LastPartIsLocal(DefaultOnToggle):
    """
    Force collecting the Secret Safe to give a ship part.
    Since you complete Pikmin 1 by collecting the last ship part, it could give a required item for another player.
    This option prevents this, so other players won't ever need to wait for Pikmin to finish.
    """
    display_name = "Local Last Part"


# ====================================================================
# PIKMIN LOCATION
# ====================================================================
class EnablePikminLocations(Toggle):
    """Enable generation of locations based on Pikmin collection thresholds
    Total Max Locations : 300"""
    display_name = "Enable Pikmin Collection Locations"
    default = False


class RedPikminLocationsEnabled(Toggle):
    """Enable Red Pikmin collection locations (no ship part requirements)
    Total Max Locations : 100"""
    display_name = "Red Pikmin Locations"
    default = True


class RedPikminInterval(Range):
    """Pikmin count interval for Red locations (e.g., 12 = 12, 24, 36... locations)"""
    display_name = "Red Pikmin Interval"
    range_start = 1
    range_end = 100
    default = 5


class YellowPikminLocationsEnabled(Toggle):
    """Enable Yellow Pikmin collection locations (requires 1 ship part)
    Total Max Locations : 100"""
    display_name = "Yellow Pikmin Locations"
    default = True


class YellowPikminInterval(Range):
    """Pikmin count interval for Yellow locations"""
    display_name = "Yellow Pikmin Interval"
    range_start = 1
    range_end = 100
    default = 5


class BluePikminLocationsEnabled(Toggle):
    """Enable Blue Pikmin collection locations (requires 5 ship parts)
    Total Max Locations : 100"""
    display_name = "Blue Pikmin Locations"
    default = True


class BluePikminInterval(Range):
    """Pikmin count interval for Blue locations"""
    display_name = "Blue Pikmin Interval"
    range_start = 1
    range_end = 100
    default = 5


# ====================================================================
# FILLER WEIGHTS
# Each option controls the weight (likelihood) of that filler item
# appearing in the item pool. A weight of 0 disables the item entirely.
# ====================================================================

class Weight1RedPikmin(Range):
    """Weight for 1 Red Pikmin filler items."""
    display_name = "1 Red Pikmin Weight"
    range_start = 0
    range_end = 100
    default = 10


class Count5RedPikmin(Range):
    """Number of 5 Red Pikmin filler items to include in the pool (0-5)."""
    display_name = "5 Red Pikmin Count"
    range_start = 0
    range_end = 5
    default = 3


class Count10RedPikmin(Range):
    """Number of 10 Red Pikmin filler items to include in the pool (0-5)."""
    display_name = "10 Red Pikmin Count"
    range_start = 0
    range_end = 5
    default = 2


class Include25RedPikmin(Toggle):
    """Include one 25 Red Pikmin filler item in the pool."""
    display_name = "Include 25 Red Pikmin"
    default = False


class Weight1YellowPikmin(Range):
    """Weight for 1 Yellow Pikmin filler items."""
    display_name = "1 Yellow Pikmin Weight"
    range_start = 0
    range_end = 100
    default = 10


class Count5YellowPikmin(Range):
    """Number of 5 Yellow Pikmin filler items to include in the pool (0-5)."""
    display_name = "5 Yellow Pikmin Count"
    range_start = 0
    range_end = 5
    default = 3


class Count10YellowPikmin(Range):
    """Number of 10 Yellow Pikmin filler items to include in the pool (0-5)."""
    display_name = "10 Yellow Pikmin Count"
    range_start = 0
    range_end = 5
    default = 2


class Include25YellowPikmin(Toggle):
    """Include one 25 Yellow Pikmin filler item in the pool."""
    display_name = "Include 25 Yellow Pikmin"
    default = False


class Weight1BluePikmin(Range):
    """Weight for 1 Blue Pikmin filler items."""
    display_name = "1 Blue Pikmin Weight"
    range_start = 0
    range_end = 100
    default = 10


class Count5BluePikmin(Range):
    """Number of 5 Blue Pikmin filler items to include in the pool (0-5)."""
    display_name = "5 Blue Pikmin Count"
    range_start = 0
    range_end = 5
    default = 3


class Count10BluePikmin(Range):
    """Number of 10 Blue Pikmin filler items to include in the pool (0-5)."""
    display_name = "10 Blue Pikmin Count"
    range_start = 0
    range_end = 5
    default = 2


class Include25BluePikmin(Toggle):
    """Include one 25 Blue Pikmin filler item in the pool."""
    display_name = "Include 25 Blue Pikmin"
    default = False


# ====================================================================
# TRAP (WIP AND DOES NOT WORKING)
# ====================================================================
class TrapPercentage(Range):
    """Percentage of filler items that are traps. Default is 0%."""
    display_name = "Trap Percentage"
    range_start = 0
    range_end = 100
    default = 0
# Trap weights (traps not yet implemented, weights reserved for future use)
class WeightTimeTrap(Range):
    """Weight for Time Trap items (reduces remaining day time)."""
    display_name = "Time Trap Weight"
    range_start = 0
    range_end = 100
    default = 0


class WeightEndDayTrap(Range):
    """Weight for End Day Trap items (forces end of current day)."""
    display_name = "End Day Trap Weight"
    range_start = 0
    range_end = 100
    default = 0


class WeightDamageTrap(Range):
    """Weight for Damage Trap items (deals damage to Pikmin)."""
    display_name = "Damage Trap Weight"
    range_start = 0
    range_end = 100
    default = 0

# ====================================================================
# QALITY OF LIFE (QOL)
# DAY CYCLE MODE
# ====================================================================

class DayCycleMode(Choice):
    """
    Controls how the day counter is managed.

    normal       : Day cycles between 2 and 29 (default Pikmin behavior without cheats)
    custom_range : Day cycles between two values chosen by the player
    fixed      : Day is locked on a fixed value chosen by the player
    """
    display_name = "Day Cycle Mode"
    option_normal       = 0
    option_custom_range = 1
    option_fixed      = 2
    default = 0


class DayCycleMin(Range):
    """Minimum day number for custom range mode. Only used when Day Cycle Mode is custom_range."""
    display_name = "Day Cycle Minimum"
    range_start = 2
    range_end = 29
    default = 2


class DayCycleMax(Range):
    """Maximum day number for custom range mode. Only used when Day Cycle Mode is custom_range."""
    display_name = "Day Cycle Maximum"
    range_start = 1
    range_end = 29
    default = 29


class DayCycleFixed(Range):
    """Fixed day number for fixed mode. Only used when Day Cycle Mode is Fixed."""
    display_name = "Day Cycle Fixed"
    range_start = 2
    range_end = 29
    default = 2


@dataclass
class P1Options(PerGameCommonOptions):
# SHIP PART
    first_part_is_local: FirstPartIsLocal
    last_part_is_local: LastPartIsLocal
# PIKMIN LOCATION
    enable_pikmin_locations: EnablePikminLocations
    red_pikmin_locations_enabled: RedPikminLocationsEnabled
    red_pikmin_interval: RedPikminInterval
    yellow_pikmin_locations_enabled: YellowPikminLocationsEnabled
    yellow_pikmin_interval: YellowPikminInterval
    blue_pikmin_locations_enabled: BluePikminLocationsEnabled
    blue_pikmin_interval: BluePikminInterval
# FILLER WEIGHTS
    weight_1_red_pikmin: Weight1RedPikmin
    count_5_red_pikmin: Count5RedPikmin
    count_10_red_pikmin: Count10RedPikmin
    include_25_red_pikmin: Include25RedPikmin
    weight_1_yellow_pikmin: Weight1YellowPikmin
    count_5_yellow_pikmin: Count5YellowPikmin
    count_10_yellow_pikmin: Count10YellowPikmin
    include_25_yellow_pikmin: Include25YellowPikmin
    weight_1_blue_pikmin: Weight1BluePikmin
    count_5_blue_pikmin: Count5BluePikmin
    count_10_blue_pikmin: Count10BluePikmin
    include_25_blue_pikmin: Include25BluePikmin
# TRAP (WIP AND DOES NOT WORKING)
    trap_percentage: TrapPercentage
    weight_time_trap: WeightTimeTrap
    weight_end_day_trap: WeightEndDayTrap
    weight_damage_trap: WeightDamageTrap
# QALITY OF LIFE (QOL) :
# - DAY CYCLE MODE
    day_cycle_mode: DayCycleMode
    day_cycle_min: DayCycleMin
    day_cycle_max: DayCycleMax
    day_cycle_fixed: DayCycleFixed