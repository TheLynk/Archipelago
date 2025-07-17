import typing
from BaseClasses import Location
from dataclasses import dataclass


@dataclass
class PikminLocationData:
    code: int
    region: str


class PikminLocation(Location):
    game: str = "Pikmin 1"


# Base location ID for Pikmin 1
base_id = 0x500000

# Location table
location_table: typing.Dict[str, PikminLocationData] = {
    # Pikmin collection milestones
    "Pikmin Rouge 10": PikminLocationData(
        code=base_id + 1,
        region="The Forest of Hope"
    ),
    "Pikmin Rouge 20": PikminLocationData(
        code=base_id + 2,
        region="The Forest of Hope"
    ),
    
    # Additional locations for testing
    "First Ship Part": PikminLocationData(
        code=base_id + 10,
        region="The Forest of Hope"
    ),
    "Second Ship Part": PikminLocationData(
        code=base_id + 11,
        region="The Forest of Hope"
    ),
    "Third Ship Part": PikminLocationData(
        code=base_id + 12,
        region="The Forest of Hope"
    ),
}

# All location names
location_names = frozenset(location_table.keys())