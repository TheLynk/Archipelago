import logging
import os
from dataclasses import fields
from typing import ClassVar, Callable, Any

from BaseClasses import Item, ItemClassification, Location, Region, CollectionState
from worlds.AutoWorld import World
from worlds.LauncherComponents import launch_subprocess, Type, components, icon_paths, Component, SuffixIdentifier
from settings import get_settings, Settings
from NetUtils import convert_to_base_types
import Utils

from .P1Data import *
from .P1Macros import *
from .P1Options import P1Options
from .P1Web import P1Web
from .P1PikminLocations import PikminLocationGenerator, PikminLocationData
from .Hints import get_hints_by_option
from .P1Rom import P1PlayerContainer, patch_iso, verify_iso, InvalidISOError

logger = logging.getLogger(__name__)


def run_client(*args) -> None:
    from .P1Client import run_client as _run_client
    launch_subprocess(_run_client, name="PikminClient", args=args)


if not any(c.display_name == "Pikmin Client" for c in components):
    components.append(
        Component(
            "Pikmin Client",
            func=run_client,
            component_type=Type.CLIENT,
            file_identifier=SuffixIdentifier(".appik1"),
            icon="Pikmin",
        )
    )
icon_paths["Pikmin"] = "ap:worlds.pikmin/assets/icon.png"


def get_base_rom_path() -> str:
    """Gets the Pikmin 1 PAL ISO path from host.yml (pikmin_options.iso_file)."""
    options: Settings = get_settings()
    file_name = options.get("pikmin_options", {}).get("iso_file", "")
    if not file_name:
        return ""
    if not os.path.exists(file_name):
        file_name = Utils.user_path(file_name)
    return file_name


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

    item_name_groups: ClassVar[dict[str, set[str]]] = {
        "Ship Part": set(ALL_PARTS.keys()),
    }

    location_name_to_id: ClassVar[dict[str, int]] = {
        **ALL_LOCATIONS,
        **PIKMIN_LOCATIONS_MAP,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pikmin_locations: dict[str, PikminLocationData] = {}
        self.hints: dict = {}

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
        menu = Region("Area Select", self.player, self.multiworld)
        self.multiworld.regions.append(menu)

        regions: dict[str, Region] = {}

        for area in Area.__args__:
            regions[area] = Region(area, self.player, self.multiworld)
            self.multiworld.regions.append(regions[area])

            regions[area].connect(menu, f"Leave {area}",
                                  (lambda state: state.has_from_list(ALL_PARTS.keys(), self.player, 1))
                                  if area == "The Impact Site" else None)
            menu.connect(regions[area], f"Enter {area}",
                         lambda state, area=area: can_access[area](state, self.player))

        for name, data in ALL_PARTS.items():
            regions[data.area].locations.append(
                P1Location(self.player, f"{name} Location", data.ap_id, regions[data.area]))

        if self.options.enable_pikmin_locations:
            self._create_pikmin_locations(regions)

    def _create_pikmin_locations(self, regions: dict[str, Region]) -> None:
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
            loc_id = PIKMIN_LOCATIONS_MAP[loc_name]
            impact_site.locations.append(
                P1Location(self.player, loc_name, loc_id, impact_site)
            )

    def create_items(self) -> None:
        items = []

        for part in ALL_PARTS:
            items.append(self.create_item(part))

        if self.options.first_part_is_local:
            self.get_location("Main Engine Location").place_locked_item(
                items.pop(self.multiworld.random.randint(0, len(items) - 1)))

        if self.options.last_part_is_local:
            self.get_location("Secret Safe Location").place_locked_item(
                items.pop(self.multiworld.random.randint(0, len(items) - 1)))

        ship_part_locations = len(ALL_PARTS)
        pikmin_location_count = len(self.pikmin_locations) if self.options.enable_pikmin_locations else 0
        total_locations = ship_part_locations + pikmin_location_count
        total_items = len(items)
        fillers_needed = max(0, total_locations - total_items)

        filler_pool = self._build_filler_pool(fillers_needed)
        for name in filler_pool:
            items.append(self.create_item(name))

        self.multiworld.itempool += items

    def _build_filler_pool(self, count: int) -> list[str]:
        if count == 0:
            return []

        fixed_items: list[str] = []
        if self.options.include_25_red_pikmin:
            fixed_items.append("25 Red Pikmin")
        if self.options.include_25_yellow_pikmin:
            fixed_items.append("25 Yellow Pikmin")
        if self.options.include_25_blue_pikmin:
            fixed_items.append("25 Blue Pikmin")
        fixed_items += ["10 Red Pikmin"] * self.options.count_10_red_pikmin.value
        fixed_items += ["10 Yellow Pikmin"] * self.options.count_10_yellow_pikmin.value
        fixed_items += ["10 Blue Pikmin"] * self.options.count_10_blue_pikmin.value
        fixed_items += ["5 Red Pikmin"] * self.options.count_5_red_pikmin.value
        fixed_items += ["5 Yellow Pikmin"] * self.options.count_5_yellow_pikmin.value
        fixed_items += ["5 Blue Pikmin"] * self.options.count_5_blue_pikmin.value

        remaining = max(0, count - len(fixed_items))

        weights: dict[str, int] = {
            "Red Pikmin":    self.options.weight_1_red_pikmin.value,
            "Yellow Pikmin": self.options.weight_1_yellow_pikmin.value,
            "Blue Pikmin":   self.options.weight_1_blue_pikmin.value,
        }

        weights = {k: v for k, v in weights.items() if v > 0}
        if not weights:
            weights = {"Red Pikmin": 1, "Yellow Pikmin": 1, "Blue Pikmin": 1}

        trap_count = int(remaining * self.options.trap_percentage.value / 100)
        filler_count = remaining - trap_count

        names = list(weights.keys())
        ws = list(weights.values())

        result = fixed_items + self.multiworld.random.choices(names, weights=ws, k=filler_count)
        # result += ["Time Trap"] * trap_count

        return result

    def set_rules(self) -> None:
        for name, data in ALL_PARTS.items():
            self.get_location(f"{name} Location").access_rule = lambda state, data=data: \
                (not data.required_types.red or can_obtain_reds(state, self.player)) \
                and (not data.required_types.yellow or can_obtain_yellows(state, self.player)) \
                and (not data.required_types.blue or can_obtain_blues(state, self.player))

        if self.options.enable_pikmin_locations:
            self._set_pikmin_location_rules()

        self.set_event("The Final Trial", "Collect All Ship Parts", "Victory", lambda state: \
            state.has_from_list(ALL_PARTS.keys(), self.player, 30))
        self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)

    def _set_pikmin_location_rules(self) -> None:
        for loc_name, loc_data in self.pikmin_locations.items():
            location = self.get_location(loc_name)

            if loc_data.required_ship_parts == 0:
                location.access_rule = lambda state: True
            elif loc_data.required_ship_parts == 1:
                location.access_rule = lambda state, parts=1: \
                    state.has_from_list(ALL_PARTS.keys(), self.player, parts)
            elif loc_data.required_ship_parts == 5:
                location.access_rule = lambda state, parts=5: \
                    state.has_from_list(ALL_PARTS.keys(), self.player, parts)

    def generate_output(self, output_directory: str) -> None:
        """Generate the .appik1 patch file for this player.

        The .appik1 is a zip containing the JSON data (seed, slot, options, hints).
        The ISO is NOT included — the user patches their own ISO when they open
        the .appik1 in the Pikmin Client (which calls patch_iso() from P1Rom.py).
        """
        seed_name = self.multiworld.seed_name
        if seed_name.startswith("W"):
            seed_name = seed_name[1:]

        output_data: dict[str, Any] = {
            "Seed":    seed_name,
            "Slot":    self.player,
            "Name":    self.player_name,
            "Options": {},
            "Hints":   self.hints,
        }

        for field in fields(self.options):
            if field.name == "plando_items":
                continue
            output_data["Options"][field.name] = getattr(self.options, field.name).value

        patch_path = os.path.join(
            output_directory,
            f"{self.multiworld.get_out_file_name_base(self.player)}"
            f"{P1PlayerContainer.patch_file_ending}"
        )

        container = P1PlayerContainer(
            output_data=output_data,
            patch_path=patch_path,
            player_name=self.player_name,
            player=self.player,
        )
        container.write()
        logger.info(f"[Pikmin] Generated {os.path.basename(patch_path)}")

    def fill_slot_data(self) -> dict:
        seed_name = self.multiworld.seed_name
        if seed_name.startswith("W"):
            seed_name = seed_name[1:]
        suffix = seed_name[-3:] if len(seed_name) >= 3 else seed_name.ljust(3, "0")

        return {
            "day_cycle_mode":      self.options.day_cycle_mode.value,
            "day_cycle_min":       self.options.day_cycle_min.value,
            "day_cycle_max":       self.options.day_cycle_max.value,
            "day_cycle_fixed":     self.options.day_cycle_fixed.value,
            "ship_part_hint_mode": self.options.ship_part_hint_mode.value,
            "hints":               self.hints,
            "game_id_suffix":      suffix,
        }

    def post_fill(self) -> None:
        get_hints_by_option(self.multiworld, {self.player})


class P1Item(Item):
    game = P1World.game


class P1Location(Location):
    game = P1World.game