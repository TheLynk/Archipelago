# pyright: reportMissingImports=false
from dataclasses import dataclass
from typing import Any

from Options import (
    Choice,
    DeathLink,
    DefaultOnToggle,
    Range,
    PerGameCommonOptions,
    StartInventoryPool,
    Toggle,
)

class OnionTypeProgression(Choice):
    """
    Choice 1 : vanilla | Red (starting with) -> Yellow -> Blue
    Choice 2 : Random order | Onion 1 Red (starting with) -> Onion 2 -> Onion 3
    """

    display_name = "Onion Type Progression"
    option_vanilla = 0
    option_random_order = 1
    default = 0

class UnlockAreaTypeProgression(Choice):
    """
    Choice 1 : vanilla | The Impact Site (starting with) -> The Forest of Hope -> The Forest Navel -> The Distant Spring -> The Final Trial
    Choice 2 : Random order | Area 1 (starting with) -> Area 2 -> Area 3 -> Area 4 -> Area 5 
    Choice 3 : Open Area | All Area is Unlock on starting run (you risk of BK is weak)
    """

    display_name = "Unlock Area Progression"
    option_vanilla = 0
    option_random_order = 1
    option_open_area = 2
    default = 0

@dataclass
class PikminOptions(PerGameCommonOptions):
    """
    a data class that encapsulates all configuration options for Pikmin
    """

    start_inventory_from_pool: StartInventoryPool
    Onion_Type_Progression: OnionTypeProgression
    Unlock_Area_Type_Progression: UnlockAreaTypeProgression

    def get_slot_data_dict(self) -> dict[str, Any]:
        return self.as_dict(
            "start_inventory_from_pool",
            "Onion_Type_Progression",
            "Unlock_Area_Type_Progression",
        )

    def get_output_dict(self) -> dict[str, Any]:
        return self.as_dict(
            "start_inventory_from_pool",
            "Onion_Type_Progression",
            "Unlock_Area_Type_Progression",
        )

