import logging
import os
from dataclasses import fields
from typing import ClassVar, Callable, Any

from BaseClasses import Item, ItemClassification, Location, Region, CollectionState
from worlds.AutoWorld import World
from worlds.LauncherComponents import launch, Type, components, icon_paths, Component, SuffixIdentifier
import settings
from settings import get_settings, Settings
from NetUtils import convert_to_base_types
import Utils

from .P1Data import *
from .P1Macros import *
from .P1Options import P1Options
from .P1Web import P1Web
from .P1PikminLocations import PikminLocationGenerator, PikminLocationData
from .Hints import get_hints_by_option
from .P1Rom import (P1PlayerContainer, patch_iso, verify_iso, InvalidISOError, expected_iso_help,
                    make_game_id_suffix)

logger = logging.getLogger(__name__)


def _apworld_version() -> str:
    """Return the apworld version from archipelago.json (works unpacked or as .apworld)."""
    import json
    try:
        from importlib.resources import files
        return json.loads((files(__package__) / "archipelago.json").read_text(encoding="utf-8")).get("version", "unknown")
    except Exception:
        pass
    try:
        with open(os.path.join(os.path.dirname(__file__), "archipelago.json"), encoding="utf-8") as f:
            return json.load(f).get("version", "unknown")
    except Exception:
        return "unknown"


def run_client(*args) -> None:
    from .P1Client import run_client as _run_client
    # Use `launch` rather than `launch_subprocess`: when the Launcher was already
    # re-run in a subprocess to open an .appik1, kivy is not running in this
    # process, so the client runs in place instead of forking another process.
    launch(_run_client, name="PikminClient", args=args)


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


PAL_GAME_ID = b"GPIP01"
NTSC_GAME_ID = b"GPIE01"
VALID_GAME_IDS = (PAL_GAME_ID, NTSC_GAME_ID)


def _validate_iso(path: str, expected: bytes, label: str) -> None:
    """Validate an ISO by Game ID rather than MD5.

    Valid dumps have different MD5s depending on revision/redump, but the first
    6 bytes (Game ID) are reliable. Already-patched ISOs (prefix P1P for PAL,
    P1E for NTSC) are rejected.
    """
    with open(path, "rb") as f:
        game_id = f.read(6)
    if game_id[:3] in (b"P1P", b"P1E"):
        raise ValueError(
            "This ISO is already patched. Please provide a clean Pikmin 1 ISO."
            + expected_iso_help(path)
        )
    if game_id != expected:
        raise ValueError(
            f"Invalid Game ID: {game_id!r}. Expected {expected.decode()} ({label})."
            + expected_iso_help(path)
        )


class PikminSettings(settings.Group):
    class ISOFile(settings.UserFilePath):
        """Path to your original, unpatched Pikmin 1 PAL ISO (GPIP01)."""
        description = "Pikmin 1 PAL ISO (unpatched)"
        # Do not copy the ISO into the Archipelago folder; keep a link to the user's file.
        copy_to = None

        @classmethod
        def validate(cls, path: str) -> None:
            _validate_iso(path, PAL_GAME_ID, "PAL")

    class ISOFileNTSC(settings.UserFilePath):
        """Path to your original, unpatched Pikmin 1 NTSC-U ISO (GPIE01)."""
        description = "Pikmin 1 NTSC-U ISO (unpatched)"
        copy_to = None

        @classmethod
        def validate(cls, path: str) -> None:
            _validate_iso(path, NTSC_GAME_ID, "NTSC-U")

    iso_file: ISOFile = ISOFile("Pikmin.iso")
    iso_file_ntsc: ISOFileNTSC = ISOFileNTSC("Pikmin_NTSC.iso")


def get_base_rom_path(game_id: bytes = PAL_GAME_ID) -> str:
    """Return the Pikmin 1 ISO path for the requested version.

    Goes through Archipelago's settings system: if the entry is missing from
    host.yaml or points to a nonexistent file, AP opens a native file picker
    and saves the choice in host.yaml.
    """
    options = get_settings().pikmin_options
    iso_file = options.iso_file_ntsc if game_id == NTSC_GAME_ID else options.iso_file
    return iso_file.resolve()


class P1World(World):
    """Pikmin 1 yay"""

    game: ClassVar[str] = "Pikmin"

    web: ClassVar[P1Web] = P1Web()

    settings_key: ClassVar[str] = "pikmin_options"
    settings: ClassVar[PikminSettings]

    options_dataclass = P1Options
    options: P1Options

    origin_region_name: str = "The Impact Site"

    item_name_to_id: ClassVar[dict[str, int]] = {
        **{name: data.ap_id for name, data in ALL_PARTS.items()},
        **FILLER_ITEMS,
        **TRAP_ITEMS,
        **USEFUL_ITEMS,
    }

    item_name_groups: ClassVar[dict[str, set[str]]] = {
        "Ship Part": set(ALL_PARTS.keys()),
        "Trap": set(TRAP_ITEMS.keys()),
    }

    location_name_to_id: ClassVar[dict[str, int]] = {
        **ALL_LOCATIONS,
        **PIKMIN_LOCATIONS_MAP,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pikmin_locations: dict[str, PikminLocationData] = {}
        self.hints: dict = {}

    # --- Universal Tracker ---------------------------------------------------
    # UT can regenerate the world without a YAML, from the server's slot_data.
    ut_can_gen_without_yaml: ClassVar[bool] = True

    # Options that change locations / logic: UT must restore them from slot_data
    # to recreate exactly the same locations and rules.
    _UT_OPTIONS: ClassVar[tuple[str, ...]] = (
        "enable_pikmin_locations",
        "red_pikmin_locations_enabled", "red_pikmin_interval",
        "yellow_pikmin_locations_enabled", "yellow_pikmin_interval",
        "blue_pikmin_locations_enabled", "blue_pikmin_interval",
        "disable_pikmin_trip",
    )

    @staticmethod
    def interpret_slot_data(slot_data: dict) -> dict:
        """Called by UT on connect; the result is passed to generate_early
        via multiworld.re_gen_passthrough."""
        return slot_data

    def generate_early(self) -> None:
        passthrough = getattr(self.multiworld, "re_gen_passthrough", None) or {}
        slot_data = passthrough.get(self.game)
        if not slot_data:
            return  # normal generation
        for name in self._UT_OPTIONS:
            if name in slot_data:
                getattr(self.options, name).value = slot_data[name]

    def create_item(self, name: str) -> "P1Item":
        if name in TRAP_ITEMS:
            return P1Item(name, ItemClassification.trap, TRAP_ITEMS[name], self.player)
        if name in FILLER_ITEMS:
            return P1Item(name, ItemClassification.filler, FILLER_ITEMS[name], self.player)
        if name in USEFUL_ITEMS:
            return P1Item(name, ItemClassification.useful, USEFUL_ITEMS[name], self.player)
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
                P1Location(self.player, ship_part_location_name(name), data.ap_id, regions[data.area]))

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

        # Disable Pikmin Trip in "item" mode: add the Useful upgrade to the pool.
        # Added before the filler count is computed so it replaces a filler
        # (total item count stays equal to the total location count).
        if self.options.disable_pikmin_trip == 2:  # option_item
            items.append(self.create_item("Trip Immunity"))

        if self.options.first_part_is_local:
            self.get_location(ship_part_location_name("Main Engine")).place_locked_item(
                items.pop(self.multiworld.random.randint(0, len(items) - 1)))

        if self.options.last_part_is_local:
            self.get_location(ship_part_location_name("Secret Safe")).place_locked_item(
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

        # All 18 pikmin bonus items with their weights from options
        weights: dict[str, int] = {
            "1 Red Leaf Pikmin":      self.options.weight_1_red_leaf.value,
            "5 Red Leaf Pikmin":      self.options.weight_5_red_leaf.value,
            "1 Red Bud Pikmin":       self.options.weight_1_red_bud.value,
            "5 Red Bud Pikmin":       self.options.weight_5_red_bud.value,
            "1 Red Flower Pikmin":    self.options.weight_1_red_flower.value,
            "5 Red Flower Pikmin":    self.options.weight_5_red_flower.value,
            "1 Yellow Leaf Pikmin":   self.options.weight_1_yellow_leaf.value,
            "5 Yellow Leaf Pikmin":   self.options.weight_5_yellow_leaf.value,
            "1 Yellow Bud Pikmin":    self.options.weight_1_yellow_bud.value,
            "5 Yellow Bud Pikmin":    self.options.weight_5_yellow_bud.value,
            "1 Yellow Flower Pikmin": self.options.weight_1_yellow_flower.value,
            "5 Yellow Flower Pikmin": self.options.weight_5_yellow_flower.value,
            "1 Blue Leaf Pikmin":     self.options.weight_1_blue_leaf.value,
            "5 Blue Leaf Pikmin":     self.options.weight_5_blue_leaf.value,
            "1 Blue Bud Pikmin":      self.options.weight_1_blue_bud.value,
            "5 Blue Bud Pikmin":      self.options.weight_5_blue_bud.value,
            "1 Blue Flower Pikmin":   self.options.weight_1_blue_flower.value,
            "5 Blue Flower Pikmin":   self.options.weight_5_blue_flower.value,
        }

        active = {k: v for k, v in weights.items() if v > 0}
        if not active:
            # Fallback: equal weight on all leaf items
            active = {k: 1 for k in weights if "Leaf" in k}

        trap_count = int(count * self.options.trap_percentage.value / 100)
        filler_count = count - trap_count

        pool: list[str] = []

        # Filler (bonus Pikmin), weighted by options.
        if filler_count > 0:
            names = list(active.keys())
            ws = list(active.values())
            pool += self.multiworld.random.choices(names, weights=ws, k=filler_count)

        # Traps, weighted by the trap weight options.
        if trap_count > 0:
            trap_weights = {
                "Time Trap":       self.options.weight_time_trap.value,
                "End Day Trap":    self.options.weight_end_day_trap.value,
                "Damage Trap":     self.options.weight_damage_trap.value,
                "Teleport Trap":   self.options.weight_teleport_trap.value,
                "Disbanding Trap": self.options.weight_disbanding_trap.value,
                "Trip Trap":       self.options.weight_trip_trap.value,
            }
            # Disable Pikmin Trip = always removes the tripping code from the ISO,
            # so a Trip Trap would have no effect: keep it out of the pool.
            if self.options.disable_pikmin_trip.value == 1:
                trap_weights.pop("Trip Trap")
            active_traps = {k: v for k, v in trap_weights.items() if v > 0}
            if not active_traps:
                # No trap weight set: distribute equally across all trap types.
                active_traps = {k: 1 for k in trap_weights}
            t_names = list(active_traps.keys())
            t_ws = list(active_traps.values())
            pool += self.multiworld.random.choices(t_names, weights=t_ws, k=trap_count)

        return pool

    def set_rules(self) -> None:
        for name, data in ALL_PARTS.items():
            self.get_location(ship_part_location_name(name)).access_rule = lambda state, data=data: \
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
            # Per-seed/per-slot Game ID suffix (3 characters).
            "GameIdSuffix": make_game_id_suffix(seed_name, self.player),
            "Options": {},
            "Hints":   self.hints,
        }

        for field in fields(self.options):
            if field.name == "plando_items":
                continue
            val = getattr(self.options, field.name).value
            # OptionSet -> sorted list (JSON-serializable).
            if isinstance(val, (set, frozenset)):
                val = sorted(val)
            output_data["Options"][field.name] = val

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
        # Same suffix as the one written into the ISO (see generate_output).
        suffix = make_game_id_suffix(seed_name, self.player)

        return {
            "normal_first_day":    self.options.normal_first_day.value,
            # 0 = off, 1 = always, 2 = item ("Trip Immunity" in the pool). Also used
            # by PopTracker to show the item only in mode 2.
            "disable_pikmin_trip": self.options.disable_pikmin_trip.value,
            "skip_events":         sorted(self.options.skip_events.value),
            "always_min_one_leaf":           self.options.always_min_one_leaf.value,
            "day_cycle_mode":      self.options.day_cycle_mode.value,
            "day_cycle_min":       self.options.day_cycle_min.value,
            "day_cycle_max":       self.options.day_cycle_max.value,
            "day_cycle_fixed":     self.options.day_cycle_fixed.value,
            "ship_part_hint_mode": self.options.ship_part_hint_mode.value,
            "hints":               self.hints,
            "game_id_suffix":      suffix,
            "death_link":          self.options.death_link.value,
            "pikmin_death_amount": self.options.pikmin_death_amount.value,
            "pikmin_bond":         self.options.pikmin_bond.value,
            "pikmin_bond_damage":  self.options.pikmin_bond_damage.value,
            # Olimar Bond (each Pikmin heals Olimar).
            "olimar_bond":         self.options.olimar_bond.value,
            "olimar_bond_heal":    self.options.olimar_bond_heal.value,
            # Damage Trap settings.
            "damage_trap_can_kill": self.options.damage_trap_can_kill.value,
            "damage_trap_amount":   self.options.damage_trap_amount.value,
            "trap_link":           self.options.trap_link.value,
            "trap_link_conversion": self.options.trap_link_conversion.value,
            # Pikmin location options and version, for PopTracker.
            "apworld_version":     _apworld_version(),
            "enable_pikmin_locations":         self.options.enable_pikmin_locations.value,
            "red_pikmin_locations_enabled":    self.options.red_pikmin_locations_enabled.value,
            "red_pikmin_interval":             self.options.red_pikmin_interval.value,
            "yellow_pikmin_locations_enabled": self.options.yellow_pikmin_locations_enabled.value,
            "yellow_pikmin_interval":          self.options.yellow_pikmin_interval.value,
            "blue_pikmin_locations_enabled":   self.options.blue_pikmin_locations_enabled.value,
            "blue_pikmin_interval":            self.options.blue_pikmin_interval.value,
            "trap_link_conversion_traps": sorted(
                t for t in self.options.trap_link_conversion_traps.value
                # Never convert to Trip Trap if tripping is removed from the game.
                if not (t == "Trip Trap" and self.options.disable_pikmin_trip.value == 1)
            ),
        }

    def post_fill(self) -> None:
        get_hints_by_option(self.multiworld, {self.player})


class P1Item(Item):
    game = P1World.game


class P1Location(Location):
    game = P1World.game