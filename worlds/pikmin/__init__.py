import logging
from typing import ClassVar, Callable

from BaseClasses import Item, ItemClassification, Location, Region, CollectionState
from worlds.AutoWorld import World
from worlds.LauncherComponents import launch_subprocess, Type, components, icon_paths, Component
from .P1Data import *
from .P1Macros import *
from .P1Options import P1Options
from .P1Web import P1Web
from .P1PikminLocations import PikminLocationGenerator, PikminLocationData

logger = logging.getLogger(__name__)


def run_client() -> None:
    from .P1Client import run_client

    launch_subprocess(run_client, name="PikminClient")


components.append(
    Component(
        "Pikmin Client",
        func=run_client,
        component_type=Type.CLIENT,
        icon="Pikmin",
    )
)
icon_paths["Pikmin"] = "ap:worlds.pikmin/assets/icon.png"


class P1World(World):
    """Pikmin 1 yay"""

    game: ClassVar[str] = "Pikmin"

    web: ClassVar[P1Web] = P1Web()

    options_dataclass = P1Options
    options: P1Options

    origin_region_name: str = "The Impact Site"

    item_name_to_id: ClassVar[dict[str, int]] = {
        **{name: data.ap_id for name, data in ALL_PARTS.items()},
        **FILLER_ITEMS,
    }

    # Item name groups allow players to use !hint Ship Part to get a hint
    # for a random ship part instead of having to name each one individually
    item_name_groups: ClassVar[dict[str, set[str]]] = {
        "Ship Part": set(ALL_PARTS.keys()),
    }

    # ALL 300 possible Pikmin locations are registered at class level, exactly like PowerWash Simulator
    # registers all its percentsanity locations. The server knows all IDs but only the locations
    # actually created in create_regions() (based on player options/interval) are active in the run.
    # The client must filter using ctx.missing_locations to only send IDs the server expects.
    location_name_to_id: ClassVar[dict[str, int]] = {
        **ALL_LOCATIONS,
        **PIKMIN_LOCATIONS_MAP,
    }

    # Will be populated with Pikmin locations if enabled
    pikmin_locations: dict[str, PikminLocationData] = {}

    def create_item(self, name: str) -> "P1Item":
        if name in FILLER_ITEMS:
            return P1Item(name, ItemClassification.filler, FILLER_ITEMS[name], self.player)
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
        logger.warning(f"[GENERATION] create_regions called, day_cycle_mode option = {self.options.day_cycle_mode.value}")
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
        self.pikmin_locations = generator.generate_locations(
            enable=self.options.enable_pikmin_locations.value,
            red_enabled=self.options.red_pikmin_locations_enabled.value,
            red_interval=self.options.red_pikmin_interval.value,
            yellow_enabled=self.options.yellow_pikmin_locations_enabled.value,
            yellow_interval=self.options.yellow_pikmin_interval.value,
            blue_enabled=self.options.blue_pikmin_locations_enabled.value,
            blue_interval=self.options.blue_pikmin_interval.value,
        )

        impact_site = regions["The Impact Site"]
        for loc_name in self.pikmin_locations:
            # Always use the ID from PIKMIN_LOCATIONS_MAP (the ClassVar source of truth),
            # NOT the sequential ID from PikminLocationGenerator which won't match.
            loc_id = PIKMIN_LOCATIONS_MAP[loc_name]
            impact_site.locations.append(
                P1Location(self.player, loc_name, loc_id, impact_site)
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

        # Calculate how many filler items are needed based on ACTUAL created locations
        ship_part_locations = len(ALL_PARTS)  # always 30
        pikmin_location_count = len(self.pikmin_locations) if self.options.enable_pikmin_locations else 0
        total_locations = ship_part_locations + pikmin_location_count
        total_items = len(items)
        fillers_needed = max(0, total_locations - total_items)

        # Build filler pool based on distribution option
        filler_pool = self._build_filler_pool(fillers_needed)
        for name in filler_pool:
            items.append(self.create_item(name))

        self.multiworld.itempool += items

    def _build_filler_pool(self, count: int) -> list[str]:
        """Build a list of filler item names based on weight options."""
        if count == 0:
            return []

        # Items added exactly once if enabled (not weighted)
        fixed_items: list[str] = []
        if self.options.include_25_red_pikmin:
            fixed_items.append("25 Red Pikmin")
        if self.options.include_25_yellow_pikmin:
            fixed_items.append("25 Yellow Pikmin")
        if self.options.include_25_blue_pikmin:
            fixed_items.append("25 Blue Pikmin")
        # 10 Pikmin items added N times (count option, max 5)
        fixed_items += ["10 Red Pikmin"] * self.options.count_10_red_pikmin.value
        fixed_items += ["10 Yellow Pikmin"] * self.options.count_10_yellow_pikmin.value
        fixed_items += ["10 Blue Pikmin"] * self.options.count_10_blue_pikmin.value
        # 5 Pikmin items added N times (count option, max 5)
        fixed_items += ["5 Red Pikmin"] * self.options.count_5_red_pikmin.value
        fixed_items += ["5 Yellow Pikmin"] * self.options.count_5_yellow_pikmin.value
        fixed_items += ["5 Blue Pikmin"] * self.options.count_5_blue_pikmin.value

        # Remaining slots filled by weighted pool
        remaining = max(0, count - len(fixed_items))

        weights: dict[str, int] = {
            "Red Pikmin":       self.options.weight_1_red_pikmin.value,
            "Yellow Pikmin":    self.options.weight_1_yellow_pikmin.value,
            "Blue Pikmin":      self.options.weight_1_blue_pikmin.value,
        }

        weights = {k: v for k, v in weights.items() if v > 0}
        if not weights:
            weights = {"Red Pikmin": 1, "Yellow Pikmin": 1, "Blue Pikmin": 1}

        trap_count = int(remaining * self.options.trap_percentage.value / 100)
        filler_count = remaining - trap_count

        names = list(weights.keys())
        ws = list(weights.values())

        result = fixed_items + self.multiworld.random.choices(names, weights=ws, k=filler_count)
        # result += ["Time Trap"] * trap_count  # uncomment when traps are added

        return result

    def set_rules(self) -> None:
        """Method for setting the rules on the World's regions and locations."""

        # alternative way of implementing local locations but this leads to randomization failures relatively often,
        # probably due to Pikmin having so few items compared to other games, therefore sometimes not having any ship
        # parts left that can be placed into these locations
        # if self.options.first_part_is_local:
        #     self.get_location("Main Engine Location").item_rule = lambda item: item.name in ALL_PARTS.keys()
        #
        # if self.options.last_part_is_local:
        #     self.get_location("Secret Safe Location").item_rule = lambda item: item.name in ALL_PARTS.keys()

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
        data = {
            "day_cycle_mode":  self.options.day_cycle_mode.value,
            "day_cycle_min":   self.options.day_cycle_min.value,
            "day_cycle_max":   self.options.day_cycle_max.value,
            "day_cycle_fixed": self.options.day_cycle_fixed.value,
        }
        logger.warning(f"[GENERATION] fill_slot_data called: {data}")
        return data


class P1Item(Item):
    game = P1World.game


class P1Location(Location):
    game = P1World.game