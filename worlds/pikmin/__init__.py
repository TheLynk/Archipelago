from typing import ClassVar, Callable

from BaseClasses import Item, ItemClassification, Location, Region, CollectionState
from worlds.AutoWorld import World
from worlds.LauncherComponents import launch_subprocess, Type, components, Component
from .P1Data import *
from .P1Macros import *
from .P1Options import P1Options
from .P1Web import P1Web
from .P1PikminLocations import PikminLocationGenerator, PikminLocationData


def run_client() -> None:
    from .P1Client import run_client

    launch_subprocess(run_client, name="PikminClient")


components.append(
    Component(
        "Pikmin Client",
        func=run_client,
        component_type=Type.CLIENT,
    )
)


class P1World(World):
    """Pikmin 1 yay"""

    game: ClassVar[str] = "Pikmin"

    web: ClassVar[P1Web] = P1Web()

    options_dataclass = P1Options
    options: P1Options

    origin_region_name: str = "The Impact Site"

    item_name_to_id: ClassVar[dict[str, int]] = {
        name: data.ap_id for name, data in ALL_PARTS.items()
    }
    
    # Add filler item to the item table
    # Use AP ID 71999 for all Carrot Pikpik instances (they all share the same ID)
    item_name_to_id["Carrot Pikpik"] = 71999

    location_name_to_id: ClassVar[dict[str, int]] = {
        f"{name} Location": data.ap_id for name, data in ALL_PARTS.items()
    }
    
    # Will be populated with Pikmin locations if enabled
    pikmin_locations: dict[str, PikminLocationData] = {}

    def create_item(self, name: str) -> "P1Item":
        if name == "Carrot Pikpik":
            return P1Item(name, ItemClassification.filler, 71999, self.player)
        return P1Item(name, ItemClassification.progression, ALL_PARTS[name].ap_id, self.player)

    def create_event(self, name: str) -> "P1Item":
        return P1Item(name, ItemClassification.progression, None, self.player)

    def set_event(self, region: str, location: str, item: str, rule: Callable[[CollectionState], bool]) -> None:
        region = self.get_region(region)
        location = P1Location(self.player, location, None, region)
        location.access_rule = rule
        region.locations.append(location)
        location.place_locked_item(self.create_event(item))

    def create_regions(self) -> None:
        menu = Region("Area Select", self.player, self.multiworld)
        self.multiworld.regions.append(menu)

        regions: dict[str, Region] = {}

        for area in Area.__args__:
            regions[area] = Region(area, self.player, self.multiworld)
            self.multiworld.regions.append(regions[area])

            # leaving impact site requires one part (to end the tutorial day)
            regions[area].connect(menu, f"Leave {area}",
                                  (lambda state: state.has_from_list(ALL_PARTS.keys(), self.player, 1))
                                  if area == "The Impact Site" else None)
            menu.connect(regions[area], f"Enter {area}",
                         lambda state, area=area: can_access[area](state, self.player))

        # Create standard ship part locations
        for name, data in ALL_PARTS.items():
            regions[data.area].locations.append(
                P1Location(self.player, f"{name} Location", data.ap_id, regions[data.area]))
        
        # Create Pikmin collection locations if enabled
        if self.options.enable_pikmin_locations:
            self._create_pikmin_locations(regions)

    def _create_pikmin_locations(self, regions: dict[str, Region]) -> None:
        """Generate and add Pikmin collection locations to regions"""
        generator = PikminLocationGenerator()
        
        # Generate locations based on options
        self.pikmin_locations = generator.generate_locations(
            enable=self.options.enable_pikmin_locations.value,
            red_enabled=self.options.red_pikmin_locations_enabled.value,
            red_interval=self.options.red_pikmin_interval.value,
            yellow_enabled=self.options.yellow_pikmin_locations_enabled.value,
            yellow_interval=self.options.yellow_pikmin_interval.value,
            blue_enabled=self.options.blue_pikmin_locations_enabled.value,
            blue_interval=self.options.blue_pikmin_interval.value,
        )
        
        # Add all generated locations to location_name_to_id
        for loc_name, loc_data in self.pikmin_locations.items():
            self.location_name_to_id[loc_name] = loc_data.ap_id
        
        # Place locations in The Impact Site region (they're checked via memory)
        impact_site = regions["The Impact Site"]
        for loc_name, loc_data in self.pikmin_locations.items():
            impact_site.locations.append(
                P1Location(self.player, loc_name, loc_data.ap_id, impact_site)
            )

    def create_items(self) -> None:
        """
        Method for creating and submitting items to the itempool. Items and Regions must *not* be created and submitted
        to the MultiWorld after this step. If items need to be placed during pre_fill use `get_pre_fill_items`.
        """
        items = []

        for part in ALL_PARTS:
            items.append(self.create_item(part))

        if self.options.first_part_is_local:
            self.get_location("Main Engine Location").place_locked_item(
                items.pop(self.multiworld.random.randint(0, len(items) - 1)))

        if self.options.last_part_is_local:
            self.get_location("Secret Safe Location").place_locked_item(
                items.pop(self.multiworld.random.randint(0, len(items) - 1)))

        # Calculate how many filler items are needed
        # Count total locations in this world
        total_locations = len(self.location_name_to_id)
        total_items = len(items)
        fillers_needed = max(0, total_locations - total_items)
        
        # Add filler items to balance locations and items
        for _ in range(fillers_needed):
            items.append(P1Item("Carrot Pikpik", ItemClassification.filler, 71999, self.player))

        self.multiworld.itempool += items

    def set_rules(self) -> None:
        """Method for setting the rules on the World's regions and locations."""

        # Set rules for standard ship part locations
        for name, data in ALL_PARTS.items():
            self.get_location(f"{name} Location").access_rule = lambda state, data=data: \
                (not data.required_types.red or can_obtain_reds(state, self.player)) \
                and (not data.required_types.yellow or can_obtain_yellows(state, self.player)) \
                and (not data.required_types.blue or can_obtain_blues(state, self.player))

        # Set rules for Pikmin collection locations if enabled
        if self.options.enable_pikmin_locations:
            self._set_pikmin_location_rules()

        self.set_event("The Final Trial", "Collect All Ship Parts", "Victory", lambda state: \
            state.has_from_list(ALL_PARTS.keys(), self.player, 30))
        self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)

    def _set_pikmin_location_rules(self) -> None:
        """Set access rules for Pikmin collection locations"""
        for loc_name, loc_data in self.pikmin_locations.items():
            location = self.get_location(loc_name)
            
            # Create a rule based on required ship parts
            if loc_data.required_ship_parts == 0:
                # Red: no requirements
                location.access_rule = lambda state: True
            elif loc_data.required_ship_parts == 1:
                # Yellow: need at least 1 ship part
                location.access_rule = lambda state, parts=1: \
                    state.has_from_list(ALL_PARTS.keys(), self.player, parts)
            elif loc_data.required_ship_parts == 5:
                # Blue: need at least 5 ship parts
                location.access_rule = lambda state, parts=5: \
                    state.has_from_list(ALL_PARTS.keys(), self.player, parts)

    def fill_slot_data(self) -> dict:
        """Send data to the client including Pikmin location IDs"""
        pikmin_locations = {}
        
        # Map all Pikmin locations to their IDs
        for loc_name, loc_id in self.location_name_to_id.items():
            if "Pikmin:" in loc_name:
                pikmin_locations[loc_name] = loc_id
        
        return {
            "pikmin_locations": pikmin_locations,
        }


class P1Item(Item):
    game = P1World.game


class P1Location(Location):
    game = P1World.game