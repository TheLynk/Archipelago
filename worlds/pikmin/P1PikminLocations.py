"""
Pikmin Locations Generator
Generates locations based on Pikmin collection thresholds
"""

from dataclasses import dataclass
from typing import Literal

Color = Literal["red", "yellow", "blue"]


@dataclass
class PikminLocationData:
    """Data for a single Pikmin collection location"""
    ap_id: int
    color: Color
    threshold: int  # At what pikmin count this location is checked
    required_ship_parts: int  # How many ship parts are required to collect this


# Memory addresses for Pikmin count by color (PAL version)
# Add more versions as needed (NTSC-U, NTSC-J, etc.)
PIKMIN_ADDRESSES = {
    b"GPIP01": {  # PAL
        "red": 0x803D6CF7,
        "yellow": 0x803D6CFB,
        "blue": 0x803D6CF3,
    },
    b"GPIE01": {  # NTSC-U
        "red": 0x803D6CF7,      # TODO: Verify NTSC-U addresses
        "yellow": 0x803D6CFB,
        "blue": 0x803D6CF3,
    },
}


class PikminLocationGenerator:
    """Generate Pikmin collection locations"""
    
    # AP ID range for Pikmin locations (71500-71999 reserved)
    PIKMIN_ID_START = 71500
    
    def __init__(self):
        self.locations: dict[str, PikminLocationData] = {}
        self.next_id = self.PIKMIN_ID_START
    
    def generate_locations(
        self,
        enable: bool,
        red_enabled: bool = True,
        red_interval: int = 5,
        yellow_enabled: bool = True,
        yellow_interval: int = 5,
        blue_enabled: bool = True,
        blue_interval: int = 5,
    ) -> dict[str, PikminLocationData]:
        """
        Generate all Pikmin locations based on configuration
        
        Args:
            enable: Master enable/disable for Pikmin locations
            red_enabled: Enable Red Pikmin locations (no requirements)
            red_interval: Threshold interval for Red (1-100)
            yellow_enabled: Enable Yellow Pikmin locations (requires 1 ship part)
            yellow_interval: Threshold interval for Yellow (1-100)
            blue_enabled: Enable Blue Pikmin locations (requires 5 ship parts)
            blue_interval: Threshold interval for Blue (1-100)
        
        Returns:
            Dictionary mapping location name to PikminLocationData
        """
        self.locations = {}
        self.next_id = self.PIKMIN_ID_START
        
        if not enable:
            return self.locations
        
        config = [
            ("red", red_enabled, red_interval, 0),      # Red needs 0 parts
            ("yellow", yellow_enabled, yellow_interval, 1),  # Yellow needs 1 part
            ("blue", blue_enabled, blue_interval, 5),    # Blue needs 5 parts
        ]
        
        for color, enabled, interval, required_parts in config:
            if enabled and 1 <= interval <= 100:
                self._generate_color_locations(color, interval, required_parts)
        
        return self.locations
    
    def _generate_color_locations(
        self,
        color: Color,
        interval: int,
        required_parts: int
    ) -> None:
        """Generate locations for a specific color"""
        current = interval
        max_pikmin = 100
        color_cap = color.capitalize()
        
        while current <= max_pikmin:
            location_name = f"{color_cap} Pikmin: {current}"
            
            self.locations[location_name] = PikminLocationData(
                ap_id=self.next_id,
                color=color,
                threshold=current,
                required_ship_parts=required_parts
            )
            
            self.next_id += 1
            current += interval
    
    def get_location_count(self, color: Color) -> int:
        """Get count of locations for a specific color"""
        return sum(1 for loc in self.locations.values() if loc.color == color)
    
    def get_total_location_count(self) -> int:
        """Get total count of all Pikmin locations"""
        return len(self.locations)
    
    def get_summary(self) -> dict:
        """Get summary of generated locations"""
        return {
            "red": self.get_location_count("red"),
            "yellow": self.get_location_count("yellow"),
            "blue": self.get_location_count("blue"),
            "total": self.get_total_location_count(),
        }


# Example usage
if __name__ == "__main__":
    gen = PikminLocationGenerator()
    
    # Example 1: Interval of 12 for each color
    locs = gen.generate_locations(
        enable=True,
        red_interval=12,
        yellow_interval=12,
        blue_interval=12,
    )
    
    print("Example 1 - Interval 12 for all colors:")
    print(f"Summary: {gen.get_summary()}")
    print(f"Red locations: {[loc for loc in locs if locs[loc].color == 'red']}\n")
    
    # Example 2: Interval of 1 (100 per color)
    gen2 = PikminLocationGenerator()
    locs2 = gen2.generate_locations(
        enable=True,
        red_interval=1,
        yellow_interval=1,
        blue_interval=1,
    )
    print("Example 2 - Interval 1 for all colors:")
    print(f"Summary: {gen2.get_summary()}")