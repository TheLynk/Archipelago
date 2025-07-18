from dataclasses import dataclass
from Options import PerGameCommonOptions, DeathLink

@dataclass
class PikminOptions(PerGameCommonOptions):
    """Options for the Pikmin world."""
    death_link: DeathLink