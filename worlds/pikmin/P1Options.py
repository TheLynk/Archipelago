from dataclasses import dataclass
from Options import DefaultOnToggle, Toggle, Range, Choice, OptionSet, PerGameCommonOptions
from .P1Symbols import SKIP_EVENT_ALL_KEYS


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
# Controls the weight (likelihood) of each pikmin filler item appearing.
# Items: 1 and 5 pikmin × 3 colors × 3 stages (Leaf / Bud / Flower)
# A weight of 0 disables that item entirely.
# ====================================================================

# --- Red ---
class Weight1RedLeaf(Range):
    """Weight for '1 Red Leaf Pikmin' filler items."""
    display_name = "1 Red Leaf Pikmin Weight"
    range_start = 0; range_end = 100; default = 10

class Weight5RedLeaf(Range):
    """Weight for '5 Red Leaf Pikmin' filler items."""
    display_name = "5 Red Leaf Pikmin Weight"
    range_start = 0; range_end = 100; default = 5

class Weight1RedBud(Range):
    """Weight for '1 Red Bud Pikmin' filler items."""
    display_name = "1 Red Bud Pikmin Weight"
    range_start = 0; range_end = 100; default = 5

class Weight5RedBud(Range):
    """Weight for '5 Red Bud Pikmin' filler items."""
    display_name = "5 Red Bud Pikmin Weight"
    range_start = 0; range_end = 100; default = 3

class Weight1RedFlower(Range):
    """Weight for '1 Red Flower Pikmin' filler items."""
    display_name = "1 Red Flower Pikmin Weight"
    range_start = 0; range_end = 100; default = 3

class Weight5RedFlower(Range):
    """Weight for '5 Red Flower Pikmin' filler items."""
    display_name = "5 Red Flower Pikmin Weight"
    range_start = 0; range_end = 100; default = 2

# --- Yellow ---
class Weight1YellowLeaf(Range):
    """Weight for '1 Yellow Leaf Pikmin' filler items."""
    display_name = "1 Yellow Leaf Pikmin Weight"
    range_start = 0; range_end = 100; default = 10

class Weight5YellowLeaf(Range):
    """Weight for '5 Yellow Leaf Pikmin' filler items."""
    display_name = "5 Yellow Leaf Pikmin Weight"
    range_start = 0; range_end = 100; default = 5

class Weight1YellowBud(Range):
    """Weight for '1 Yellow Bud Pikmin' filler items."""
    display_name = "1 Yellow Bud Pikmin Weight"
    range_start = 0; range_end = 100; default = 5

class Weight5YellowBud(Range):
    """Weight for '5 Yellow Bud Pikmin' filler items."""
    display_name = "5 Yellow Bud Pikmin Weight"
    range_start = 0; range_end = 100; default = 3

class Weight1YellowFlower(Range):
    """Weight for '1 Yellow Flower Pikmin' filler items."""
    display_name = "1 Yellow Flower Pikmin Weight"
    range_start = 0; range_end = 100; default = 3

class Weight5YellowFlower(Range):
    """Weight for '5 Yellow Flower Pikmin' filler items."""
    display_name = "5 Yellow Flower Pikmin Weight"
    range_start = 0; range_end = 100; default = 2

# --- Blue ---
class Weight1BlueLeaf(Range):
    """Weight for '1 Blue Leaf Pikmin' filler items."""
    display_name = "1 Blue Leaf Pikmin Weight"
    range_start = 0; range_end = 100; default = 10

class Weight5BlueLeaf(Range):
    """Weight for '5 Blue Leaf Pikmin' filler items."""
    display_name = "5 Blue Leaf Pikmin Weight"
    range_start = 0; range_end = 100; default = 5

class Weight1BlueBud(Range):
    """Weight for '1 Blue Bud Pikmin' filler items."""
    display_name = "1 Blue Bud Pikmin Weight"
    range_start = 0; range_end = 100; default = 5

class Weight5BlueBud(Range):
    """Weight for '5 Blue Bud Pikmin' filler items."""
    display_name = "5 Blue Bud Pikmin Weight"
    range_start = 0; range_end = 100; default = 3

class Weight1BlueFlower(Range):
    """Weight for '1 Blue Flower Pikmin' filler items."""
    display_name = "1 Blue Flower Pikmin Weight"
    range_start = 0; range_end = 100; default = 3

class Weight5BlueFlower(Range):
    """Weight for '5 Blue Flower Pikmin' filler items."""
    display_name = "5 Blue Flower Pikmin Weight"
    range_start = 0; range_end = 100; default = 2


# ====================================================================
# TRAP
# ====================================================================
class TrapPercentage(Range):
    """Percentage of filler items that are traps. Default is 0% (traps off)."""
    display_name = "Trap Percentage"
    range_start = 0
    range_end = 100
    default = 0


class TrapLink(Toggle):
    """
    When enabled, traps you receive are broadcast to every other TrapLink player,
    and you receive theirs. Requires traps to be present in the item pool.
    """
    display_name = "Trap Link"


# Weight (relative likelihood) of each trap type when traps are enabled.
class WeightTimeTrap(Range):
    """Weight for Time Trap items (reduces remaining day time)."""
    display_name = "Time Trap Weight"
    range_start = 0
    range_end = 100
    default = 50


class WeightEndDayTrap(Range):
    """Weight for End Day Trap items (forces end of current day)."""
    display_name = "End Day Trap Weight"
    range_start = 0
    range_end = 100
    default = 50


class WeightDamageTrap(Range):
    """Weight for Damage Trap items (damages Olimar)."""
    display_name = "Damage Trap Weight"
    range_start = 0
    range_end = 100
    default = 50


class WeightTeleportTrap(Range):
    """Weight for Teleport Trap items (teleports Olimar to a random nearby spot)."""
    display_name = "Teleport Trap Weight"
    range_start = 0
    range_end = 100
    default = 50


class WeightDisbandingTrap(Range):
    """Weight for Disbanding Trap items (scatters your whole squad)."""
    display_name = "Disbanding Trap Weight"
    range_start = 0
    range_end = 100
    default = 50


# ====================================================================
# QUALITY OF LIFE (QOL)
# NORMAL FIRST DAY
# ====================================================================

class NormalFirstDay(DefaultOnToggle):
    """
    Play the very first day like any other day.

    Normally the first day is a tutorial: it opens with Olimar's long
    crash-landing cutscene, the day timer stays frozen, and pop-up tips keep
    interrupting you. Turn this on and the first day behaves like a normal one:
    no crash cutscene, the clock runs, and the tutorial pop-ups are skipped.
    """
    display_name = "Normal First Day"


class DisablePikminTrip(Choice):
    """
    Pikmin sometimes stumble and fall flat on their face while walking behind
    you, and stay down for a few seconds. This lets you turn that off.

    off    - Pikmin can trip, just like in the original game.
    always - Pikmin never trip, right from the start.
    item   - Pikmin can trip until you find the "Trip Immunity" item somewhere in
             the multiworld; once you get it, they never trip again. This adds one
             extra useful item to the pool.
    """
    display_name = "Disable Pikmin Trip"
    option_off    = 0
    option_always = 1
    option_item   = 2
    default = 1


class SkipEvents(OptionSet):
    """
    Choose which one-time cutscenes and tutorial messages to skip. List only the
    entries you want skipped (default: all of them). Remove an entry to keep it.

    Cutscenes:
      Onion Discovery       : short cutscene the first time you meet each Onion (red/yellow/blue).
      New Pikmin            : cutscene the first time you pluck a new colour of Pikmin from the ground.
      Main Engine Discovery : cutscene when you first find the Main Engine in The Impact Site.
      First Pellet          : cutscene the first time a pellet is carried into an Onion.
      Part Collection       : cutscene when Pikmin bring a ship part to the ship (camera, absorption
                              and its description text), plus the Main Engine's version. Ship-part
                              hints (on approach) are NOT affected. [ISO DOL patch: re-patch needed.]
      Ship Upgrade          : cutscene when the ship upgrades and a new area unlocks.
                              [ISO DOL patch: re-patch needed.]
      Box Push              : cutscene the first time your Pikmin push the big box (The Impact Site).
      First Bomb            : cutscene the first time a Yellow Pikmin brings back a bomb-rock.

    Tutorial messages:
      Pikmin Limit   : message the first time you exceed 100 Pikmin on the field.
      Bomb Explosion : message the first time a bomb-rock explodes.
      Olimar Damage  : message the first time Olimar takes damage.
      Carry Path     : message when your Pikmin can't find a path to carry an object.
      First Noon     : info message shown at noon on the first day.
      Onion Followed : message where Olimar notes the red Onion followed him (first landing).
      Nectar         : message explaining nectar the first time a Pikmin drinks some.

    Most entries are applied live by the client; "Part Collection" and
    "Ship Upgrade" are baked into the ISO at patch time (re-patch to change them).
    """
    display_name = "Skip Cutscenes and Messages"
    valid_keys = set(SKIP_EVENT_ALL_KEYS)
    default = set(SKIP_EVENT_ALL_KEYS)


class AlwaysMinOneLeaf(DefaultOnToggle):
    """
    Always keep at least one leaf-stage Pikmin of each colour around. This skips
    the "new sprouts" cutscene that plays at the start of a day when an Onion
    grows fresh Pikmin.
    """
    display_name = "Always Keep One Leaf Pikmin"


# ====================================================================
# DAY CYCLE MODE
# ====================================================================

class DayCycleMode(Choice):
    """
    Controls how the day counter is managed.

    normal       : Day cycles between 2 and 29 (default Pikmin behavior without cheats)
    custom_range : Day cycles between two values chosen by the player
    fixed        : Day is locked on a fixed value chosen by the player
    """
    display_name = "Day Cycle Mode"
    option_normal       = 0
    option_custom_range = 1
    option_fixed        = 2
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
    """Fixed day number for fixed mode. Only used when Day Cycle Mode is fixed."""
    display_name = "Day Cycle Fixed"
    range_start = 2
    range_end = 29
    default = 2


# ====================================================================
# SHIP PART HINTS
# ====================================================================

class ShipPartHintMode(Choice):
    """
    Controls what information is displayed when approaching a ship part.

    none        : No hint displayed (vanilla behavior)
    item        : Shows what item the ship part location contains
    super_radar : Shows where your progression items are located in the multiworld
    both        : Shows both the item and where progression items are located
    """
    display_name = "Ship Part Hint Mode"
    option_none = 0
    option_item = 1
    option_super_radar = 2
    option_both = 3
    default = 1


# ====================================================================
# DEATH LINK / TRAP LINK
# ====================================================================

class DeathLink(Choice):
    """
    Link deaths with the other players in your multiworld.

    off     : DeathLink disabled.
    classic : Send a DeathLink whenever Olimar goes down (dies).
    pikmin  : Send a DeathLink for every X Pikmin that die during the day
              (see Pikmin Death Amount).
    both    : Send a DeathLink when Olimar dies OR when too many Pikmin die in
              the day, and losing too many Pikmin also kills Olimar.

    In every mode, receiving a DeathLink kills Olimar.
    """
    display_name = "Death Link"
    option_off = 0
    option_classic = 1
    option_pikmin = 2
    option_both = 3
    default = 0


class PikminDeathAmount(Range):
    """
    Number of Pikmin deaths within a single day that triggers one DeathLink.
    Used when Death Link is set to 'pikmin' or 'both'. The counter resets each day.
    """
    display_name = "Pikmin Death Amount"
    range_start = 1
    range_end = 100
    default = 20


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
    weight_1_red_leaf:      Weight1RedLeaf
    weight_5_red_leaf:      Weight5RedLeaf
    weight_1_red_bud:       Weight1RedBud
    weight_5_red_bud:       Weight5RedBud
    weight_1_red_flower:    Weight1RedFlower
    weight_5_red_flower:    Weight5RedFlower
    weight_1_yellow_leaf:   Weight1YellowLeaf
    weight_5_yellow_leaf:   Weight5YellowLeaf
    weight_1_yellow_bud:    Weight1YellowBud
    weight_5_yellow_bud:    Weight5YellowBud
    weight_1_yellow_flower: Weight1YellowFlower
    weight_5_yellow_flower: Weight5YellowFlower
    weight_1_blue_leaf:     Weight1BlueLeaf
    weight_5_blue_leaf:     Weight5BlueLeaf
    weight_1_blue_bud:      Weight1BlueBud
    weight_5_blue_bud:      Weight5BlueBud
    weight_1_blue_flower:   Weight1BlueFlower
    weight_5_blue_flower:   Weight5BlueFlower
# TRAP
    trap_percentage: TrapPercentage
    trap_link: TrapLink
    weight_time_trap: WeightTimeTrap
    weight_end_day_trap: WeightEndDayTrap
    weight_damage_trap: WeightDamageTrap
    weight_teleport_trap: WeightTeleportTrap
    weight_disbanding_trap: WeightDisbandingTrap
# DEATH LINK
    death_link: DeathLink
    pikmin_death_amount: PikminDeathAmount
# QUALITY OF LIFE (QOL)
# - NORMAL FIRST DAY
    normal_first_day: NormalFirstDay
# - DISABLE PIKMIN TRIP
    disable_pikmin_trip: DisablePikminTrip
# - CUTSCENE / TEXT SKIPS (fusionnes en un seul OptionSet)
    skip_events: SkipEvents
    always_min_one_leaf: AlwaysMinOneLeaf
# - DAY CYCLE MODE
    day_cycle_mode: DayCycleMode
    day_cycle_min: DayCycleMin
    day_cycle_max: DayCycleMax
    day_cycle_fixed: DayCycleFixed
# - SHIP PART HINTS
    ship_part_hint_mode: ShipPartHintMode