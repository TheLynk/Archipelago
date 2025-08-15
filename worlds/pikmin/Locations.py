from enum import Enum, Flag, auto
from typing import TYPE_CHECKING, NamedTuple, Optional

from BaseClasses import Location, Region

class PikminFlag(Flag):
    """
    This class represents flags used for categorizing game locations.
    Flags are used to group locations by their specific gameplay or logic attributes.
    """

    ALWAYS = auto()

class PikminLocationType(Enum):
    """
    This class defines constants for various types of locations in Pikmin.
    """

    SHIP_PART = auto()
    WALL = auto()
    BRIDGE = auto()
    LAND = auto()

class PikminLocationData(NamedTuple):

    """
    This class represents the data for a location in Pikmin.

    :param code: The unique code identifier for the location.
    :param flags: The flags that categorize the location.
    :param region: The name of the region where the location resides.
    :param stage_id: The ID of the stage where the location resides.
    :param type: The type of the location.
    :param bit: The bit in memory that is associated with the location. This is combined with other location data to
    determine where in memory to determine whether the location has been checked. If the location is a special type,
    this bit is ignored.
    :param address: For certain location types, this variable contains the address of the byte with the check bit for
    that location. Defaults to `None`.
    """

    code: Optional[int]
    flags: PikminFlag
    region: str
    stage_id: int
    type: PikminLocationType
    bit: int
    address: Optional[int] = None

class PikminLocation(Location):
    """
    This class represents a location in Pikmin.

    :param player: The ID of the player whose world the location is in.
    :param name: The name of the location.
    :param parent: The location's parent region.
    :param data: The data associated with this location.
    """

    game: str = "Pikmin"

    def __init__(self, player: int, name: str, parent: Region, data: PikminLocationData):
        address = None if data.code is None else PikminLocation.get_apid(data.code)
        super().__init__(player, name, address=address, parent=parent)

        self.code = data.code
        self.flags = data.flags
        self.region = data.region
        self.stage_id = data.stage_id
        self.type = data.type
        self.bit = data.bit
        self.address = self.address

    @staticmethod
    def get_apid(code: int) -> int:
        """
        Compute the Archipelago ID for the given location code.

        :param code: The unique code for the location.
        :return: The computed Archipelago ID.
        """
        base_id: int = 2326528
        return base_id + code

LOCATION_TABLE: dict[str, PikminLocationData] = {
    # Crash Site
    "Crash Site - Crash on PNF-404": PikminLocationData(
        0, PikminFlag.ALWAYS, "Crash Site", 0xB, PikminLocationType.SHIP_PART, 5
    ),

    # Defeat Ganondorf
    "Land to the Space": PikminLocationData(
        None, PikminFlag.ALWAYS, "World Map", 0x8, PikminLocationType.LAND, 64
    ),
}

def split_location_name_by_zone(location_name: str) -> tuple[str, str]:
    """
    Split a location name into its zone name and specific name.

    :param location_name: The full name of the location.
    :return: A tuple containing the zone and specific name.
    """
    if " - " in location_name:
        zone_name, specific_location_name = location_name.split(" - ", 1)
    else:
        zone_name = specific_location_name = location_name

    return zone_name, specific_location_name