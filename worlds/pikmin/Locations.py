# pyright: reportMissingImports=false
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
    PIKMIN_NUMBER = auto()
    VISIT = auto()
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
        base_id: int = 159159
        return base_id + code

LOCATION_TABLE: dict[str, PikminLocationData] = {
    # === SHIP PARTS LOCATIONS (30 total) ===
    
    # Impact Site (2 ship parts)
    "Impact Site - Main Engine": PikminLocationData(100, PikminFlag.ALWAYS, "The Impact Site", 0x0, PikminLocationType.SHIP_PART, 0, None),
    "Impact Site - Positron Generator": PikminLocationData(101, PikminFlag.ALWAYS, "The Impact Site", 0x0, PikminLocationType.SHIP_PART, 1, None),
    
    # Forest of Hope (8 ship parts)
    "Forest of Hope - Eternal Fuel Dynamo": PikminLocationData(102, PikminFlag.ALWAYS, "The Forest of Hope", 0x1, PikminLocationType.SHIP_PART, 0, None),
    "Forest of Hope - Extraordinary Bolt": PikminLocationData(103, PikminFlag.ALWAYS, "The Forest of Hope", 0x1, PikminLocationType.SHIP_PART, 1, None),
    "Forest of Hope - Whimsical Radar": PikminLocationData(104, PikminFlag.ALWAYS, "The Forest of Hope", 0x1, PikminLocationType.SHIP_PART, 2, None),
    "Forest of Hope - Radiation Canopy": PikminLocationData(105, PikminFlag.ALWAYS, "The Forest of Hope", 0x1, PikminLocationType.SHIP_PART, 3, None),
    "Forest of Hope - Sagittarius": PikminLocationData(106, PikminFlag.ALWAYS, "The Forest of Hope", 0x1, PikminLocationType.SHIP_PART, 4, None),
    "Forest of Hope - Shock Absorber": PikminLocationData(107, PikminFlag.ALWAYS, "The Forest of Hope", 0x1, PikminLocationType.SHIP_PART, 5, None),
    "Forest of Hope - Nova Blaster": PikminLocationData(108, PikminFlag.ALWAYS, "The Forest of Hope", 0x1, PikminLocationType.SHIP_PART, 6, None),
    "Forest of Hope - Geiger Counter": PikminLocationData(109, PikminFlag.ALWAYS, "The Forest of Hope", 0x2, PikminLocationType.SHIP_PART, 0, None),
    
    # Forest Navel (9 ship parts)
    "Forest Navel - Automatic Gear": PikminLocationData(110, PikminFlag.ALWAYS, "The Forest Navel", 0x2, PikminLocationType.SHIP_PART, 1, None),
    "Forest Navel - #1 Ionium Jet": PikminLocationData(111, PikminFlag.ALWAYS, "The Forest Navel", 0x2, PikminLocationType.SHIP_PART, 2, None),
    "Forest Navel - Anti-Dioxin Filter": PikminLocationData(112, PikminFlag.ALWAYS, "The Forest Navel", 0x2, PikminLocationType.SHIP_PART, 3, None),
    "Forest Navel - Omega Stabilizer": PikminLocationData(113, PikminFlag.ALWAYS, "The Forest Navel", 0x2, PikminLocationType.SHIP_PART, 4, None),
    "Forest Navel - Gravity Jumper": PikminLocationData(114, PikminFlag.ALWAYS, "The Forest Navel", 0x2, PikminLocationType.SHIP_PART, 5, None),
    "Forest Navel - Analog Computer": PikminLocationData(115, PikminFlag.ALWAYS, "The Forest Navel", 0x2, PikminLocationType.SHIP_PART, 6, None),
    "Forest Navel - Guard Satellite": PikminLocationData(116, PikminFlag.ALWAYS, "The Forest Navel", 0x2, PikminLocationType.SHIP_PART, 7, None),
    "Forest Navel - Libra": PikminLocationData(117, PikminFlag.ALWAYS, "The Forest Navel", 0x2, PikminLocationType.SHIP_PART, 8, None),
    "Forest Navel - Space Float": PikminLocationData(118, PikminFlag.ALWAYS, "The Forest Navel", 0x2, PikminLocationType.SHIP_PART, 9, None),
    
    # Distant Spring (10 ship parts)
    "Distant Spring - Repair-type Bolt": PikminLocationData(119, PikminFlag.ALWAYS, "The Distant Spring", 0x3, PikminLocationType.SHIP_PART, 0, None),
    "Distant Spring - Gluon Drive": PikminLocationData(120, PikminFlag.ALWAYS, "The Distant Spring", 0x3, PikminLocationType.SHIP_PART, 1, None),
    "Distant Spring - Zirconium Rotor": PikminLocationData(121, PikminFlag.ALWAYS, "The Distant Spring", 0x3, PikminLocationType.SHIP_PART, 2, None),
    "Distant Spring - Interstellar Radio": PikminLocationData(122, PikminFlag.ALWAYS, "The Distant Spring", 0x3, PikminLocationType.SHIP_PART, 3, None),
    "Distant Spring - Pilot's Seat": PikminLocationData(123, PikminFlag.ALWAYS, "The Distant Spring", 0x3, PikminLocationType.SHIP_PART, 4, None),
    "Distant Spring - #2 Ionium Jet": PikminLocationData(124, PikminFlag.ALWAYS, "The Distant Spring", 0x3, PikminLocationType.SHIP_PART, 5, None),
    "Distant Spring - Bowsprit": PikminLocationData(125, PikminFlag.ALWAYS, "The Distant Spring", 0x3, PikminLocationType.SHIP_PART, 6, None),
    "Distant Spring - Chronos Reactor": PikminLocationData(126, PikminFlag.ALWAYS, "The Distant Spring", 0x3, PikminLocationType.SHIP_PART, 7, None),
    "Distant Spring - Massage Machine": PikminLocationData(127, PikminFlag.ALWAYS, "The Distant Spring", 0x3, PikminLocationType.SHIP_PART, 8, None),
    "Distant Spring - UV Lamp": PikminLocationData(128, PikminFlag.ALWAYS, "The Distant Spring", 0x3, PikminLocationType.SHIP_PART, 9, None),
    
    # Final Trial (1 ship part)
    "Final Trial - Secret Safe": PikminLocationData(129, PikminFlag.ALWAYS, "The Final Trial", 0x4, PikminLocationType.SHIP_PART, 0, None),
    
    # === PIKMIN MILESTONES (30 total) ===
    
    # Red Pikmin Milestones (10)
    "Pikmin Red - 10": PikminLocationData(1, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF7),
    "Pikmin Red - 20": PikminLocationData(2, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF7),
    "Pikmin Red - 30": PikminLocationData(3, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF7),
    "Pikmin Red - 40": PikminLocationData(4, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF7),
    "Pikmin Red - 50": PikminLocationData(5, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF7),
    "Pikmin Red - 60": PikminLocationData(6, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF7),
    "Pikmin Red - 70": PikminLocationData(7, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF7),
    "Pikmin Red - 80": PikminLocationData(8, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF7),
    "Pikmin Red - 90": PikminLocationData(9, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF7),
    "Pikmin Red - 100": PikminLocationData(10, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF7),

    # Yellow Pikmin Milestones (10)
    "Pikmin Yellow - 10": PikminLocationData(11, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CFB),
    "Pikmin Yellow - 20": PikminLocationData(12, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CFB),
    "Pikmin Yellow - 30": PikminLocationData(13, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CFB),
    "Pikmin Yellow - 40": PikminLocationData(14, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CFB),
    "Pikmin Yellow - 50": PikminLocationData(15, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CFB),
    "Pikmin Yellow - 60": PikminLocationData(16, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CFB),
    "Pikmin Yellow - 70": PikminLocationData(17, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CFB),
    "Pikmin Yellow - 80": PikminLocationData(18, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CFB),
    "Pikmin Yellow - 90": PikminLocationData(19, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CFB),
    "Pikmin Yellow - 100": PikminLocationData(20, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CFB),

    # Blue Pikmin Milestones (10)
    "Pikmin Blue - 10": PikminLocationData(21, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF3),
    "Pikmin Blue - 20": PikminLocationData(22, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF3),
    "Pikmin Blue - 30": PikminLocationData(23, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF3),
    "Pikmin Blue - 40": PikminLocationData(24, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF3),
    "Pikmin Blue - 50": PikminLocationData(25, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF3),
    "Pikmin Blue - 60": PikminLocationData(26, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF3),
    "Pikmin Blue - 70": PikminLocationData(27, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF3),
    "Pikmin Blue - 80": PikminLocationData(28, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF3),
    "Pikmin Blue - 90": PikminLocationData(29, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF3),
    "Pikmin Blue - 100": PikminLocationData(30, PikminFlag.ALWAYS, "The Crash Site", 0x0, PikminLocationType.PIKMIN_NUMBER, 0, 0x803D6CF3),

    # === VICTORY LOCATION ===
    "Land to the Space": PikminLocationData(None, PikminFlag.ALWAYS, "The Crash Site", 0x8, PikminLocationType.LAND, 1, None),
}

# TOTAL LOCATIONS: 30 (ship parts) + 30 (Pikmin milestones) = 60 locations
# Plus 1 victory location = 61 total locations 
# LOCATIONS TO FILL: 60 (excluding victory location)

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