import typing
from Options import Option, DefaultOnToggle, Range, Choice, Toggle, PerGameCommonOptions


# class StartingPikmin(Range):
#     """Number of Pikmin to start with."""
#     display_name = "Starting Pikmin Count"
#     range_start = 0
#     range_end = 50
#     default = 5


# class PikminGrowthRate(Choice):
#     """How quickly Pikmin grow from seeds."""
#     display_name = "Pikmin Growth Rate"
#     option_slow = 0
#     option_normal = 1
#     option_fast = 2
#     default = 1


# class RandomizePikminTypes(Toggle):
#     """Whether to randomize which Pikmin types are available."""
#     display_name = "Randomize Pikmin Types"
#     default = False


# class Pikmin1Options(PerGameCommonOptions):
#     starting_pikmin: StartingPikmin
#     pikmin_growth_rate: PikminGrowthRate
#     randomize_pikmin_types: RandomizePikminTypes