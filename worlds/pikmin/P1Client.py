import asyncio
import os
import time
from typing import TYPE_CHECKING, Optional

import dolphin_memory_engine as dme

import Utils
from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus
from .P1UI import P1UI
from .P1Data import *

if TYPE_CHECKING:
    import kvui

SCOUT_RETRY_INTERVAL = 5.0  # seconds between scout retries

UNLOCKED_AREAS: MemoryAddress = mem(0x803A2803, 0x8039D983)  # byte
COUNT_TOTAL_PARTS: MemoryAddress = mem(0x812427FF, 0x81249DE7)  # byte
COUNT_REQUIRED_PARTS: MemoryAddress = mem(0x81242803, 0x81249DEB)  # byte
TIME_HOURS: MemoryAddress = mem(0x803A2930, 0x803A2930)  # int, 7=morning, >=19=end of day
DAY_NUMBER: MemoryAddress = mem(0x803A2937, 0x803A2937)  # byte, current day number

# Ship part hint text address (PAL) — universal for all parts
SHIP_PART_TEXT_ADDR = 0x807B100A
SHIP_PART_TEXT_LENGTH = 313  # 0x807B1143 - 0x807B100A
BOTH_MODE_TOGGLE_INTERVAL = 5.0  # seconds


# Pikmin count addresses — used for location checking (stable, always valid)
PIKMIN_ADDRESSES_PAL = {
    "red":    0x803D6CF7,
    "yellow": 0x803D6CFB,
    "blue":   0x803D6CF3,
}

PIKMIN_ADDRESSES_NTSC_U = {
    "red":    0x803D1E77,
    "yellow": 0x803D1E7B,
    "blue":   0x803D1E73,
}

PIKMIN_ADDRESSES = {
    b"GPIP01": PIKMIN_ADDRESSES_PAL,
    b"GPIE01": PIKMIN_ADDRESSES_NTSC_U,
}

# Onion active counts — written by the patched DOL stub to fixed addresses.
# Fixed addresses written by the DOL stub each time the game updates an onion.
# VAL: current onion count (mirror of dynamic address)
# PTR: pointer to the dynamic onion address (changes per Dolphin session)
# Stable across all Dolphin versions (DOL BSS region, zeroed at boot).
ONION_VAL_ADDRS_PAL = {
    "red":    0x803D7000,
    "yellow": 0x803D7004,
    "blue":   0x803D7008,
}

# Stub stores r29 (onion base) per color — client computes dyn_addr = base + 0x042C
ONION_BASE_ADDRS_PAL = {
    "red":    0x803D7010,
    "yellow": 0x803D7014,
    "blue":   0x803D7018,
}
ONION_DYN_OFFSET = 0x042C


# Onion persistent counts — applied at the start of each new day.
ONION_PERSISTENT_ADDRS_PAL = {
    "red":    0x803D6C7E,
    "yellow": 0x803D6C8A,
    "blue":   0x803D6C72,
}

ONION_VAL_ADDRS = {b"GPIP01": ONION_VAL_ADDRS_PAL}
ONION_BASE_ADDRS = {b"GPIP01": ONION_BASE_ADDRS_PAL}
ONION_PERSISTENT_ADDRS = {b"GPIP01": ONION_PERSISTENT_ADDRS_PAL}


class P1CommandProcessor(ClientCommandProcessor):
    def __init__(self, ctx: CommonContext):
        super().__init__(ctx)

    def _cmd_debug(self) -> bool:
        """Toggle debug logging for Pikmin client."""
        self.ctx.debug_mode = not getattr(self.ctx, "debug_mode", False)
        state = "ON" if self.ctx.debug_mode else "OFF"

        if self.ctx.debug_mode:
            logger.info(f"Pikmin debug mode: {state}")
            slot_data = getattr(self.ctx, "slot_data", {}) or {}
            hint_mode = slot_data.get("ship_part_hint_mode", 0)
            hints = slot_data.get("hints", {})
            logger.info(f"[DEBUG] Hint mode: {hint_mode}")
            logger.info(f"[DEBUG] Hints count: {len(hints)}")
            if hints:
                for part_name, hint_data in hints.items():
                    logger.info(f"[DEBUG]   {part_name}: {hint_data.get('Item', '?')} at {hint_data.get('Location', '?')}")
        else:
            logger.info(f"Pikmin debug mode: {state}")

        return True

    def _cmd_crash(self) -> bool:
        """Re-apply all received Pikmin bonus items and re-check all collected ship part locations.
        Use this if the game crashed and you lost progress."""
        old_key = self.ctx._save_key()

        # Reset applied items so all bonuses get re-applied
        self.ctx.pikmin_items_applied = {}
        self.ctx.save_applied()

        new_key = self.ctx._save_key()

        # Remove ship part location IDs from checked_locations so they get re-checked
        ship_part_location_ids = {data.ap_id for data in ALL_PARTS.values()}
        self.ctx.locations_checked -= ship_part_location_ids

        logger.info(f"Crash recovery: old key = '{old_key}'")
        logger.info(f"Crash recovery: new key = '{new_key}'")
        logger.info("Crash recovery: all Pikmin bonuses will be re-applied on next tick.")
        logger.info("Crash recovery: ship part locations will be re-checked on next tick.")
        return True


class P1Context(CommonContext):
    command_processor = P1CommandProcessor
    game: str = "Pikmin"
    items_handling: int = 0b111

    def __init__(self, server_address: Optional[str], password: Optional[str]) -> None:
        super().__init__(server_address, password)
        self.dolphin_status_text = "Disconnected"

        # Track Pikmin counts for location checking
        self.pikmin_counts = {"red": 0, "yellow": 0, "blue": 0}
        self.pikmin_location_ids = {}
        self.last_red_count = 0
        self.last_yellow_count = 0
        self.last_blue_count = 0

        # Track how many Pikmin bonus items have already been applied
        self.pikmin_items_applied: dict[int, int] = {}
        # Day start detection for safety check
        self.last_hour: int = -1
        # Debug mode toggle via /debug command
        self.debug_mode: bool = False
        # Pending DYN pikmin per color (waiting for base addr to be known)
        self.pikmin_dyn_pending: dict[str, int] = {"red": 0, "yellow": 0, "blue": 0}
        # Ship part hint tracking
        self.last_hint_shown: str = ""
        # Raw bytes of the hint we wrote, so we can re-apply if the game overwrites it
        self.last_hint_bytes: bytes = b""
        # Throttle for day cycle debug logs (timestamp of last log)
        self._last_day_debug_log: float = 0.0
        # Throttle for NTSC warning (timestamp of last warning)
        self._last_ntsc_warning: float = 0.0
        # Scouted locations: loc_id -> {"item_name": str, "player": int}
        self.scouted_locations: dict[int, dict] = {}
        # Flag to trigger location scout after connection is fully established
        self.needs_location_scout: bool = False
        # Track scout state for retry logic
        self.scout_sent: bool = False
        self.scout_sent_time: float = 0.0
        self.scout_received: bool = False
        # Track which location hints have been created on the server
        self.created_hints: set[int] = set()
        # Super Radar: cache of ALL scouted locations (not just own)
        self.all_locations_scouted: dict[int, dict] = {}
        # Super Radar: track that we've requested all-locations scout
        self.super_radar_requested: bool = False
        self.super_radar_hints_created: bool = False
        # Super Radar: store hints received from server
        self.server_hints: dict[int, dict] = {}
        # Slot data received from server on connection
        self.slot_data: dict = {}
        # Both mode: toggle between item/radar display
        self.hint_both_toggle: bool = False
        self.hint_both_last_toggle: float = 0.0

    def _save_key(self) -> str:
        slot_data = getattr(self, "slot_data", {}) or {}
        suffix = slot_data.get("game_id_suffix", "")
        if suffix:
            return f"applied_{self.auth}_P1P{suffix}"
        seed = getattr(self, "seed_name", None) or "unknown"
        return f"applied_{self.auth}_{seed}"

    def load_applied(self) -> None:
        key = self._save_key()
        if self.debug_mode:
            logger.info(f"[DEBUG] load_applied key: {key}")
        try:
            data = Utils.persistent_load().get("pikmin", {}).get(self._save_key(), {})
            self.pikmin_items_applied = {int(k): v for k, v in data.items()}
            if self.debug_mode:
                logger.info(f"[DEBUG] Loaded {len(self.pikmin_items_applied)} applied Pikmin items")
        except Exception as e:
            logger.debug(f"Could not load applied items: {e}")

    def save_applied(self) -> None:
        try:
            Utils.persistent_store("pikmin", self._save_key(),
                                   {str(k): v for k, v in self.pikmin_items_applied.items()})
        except Exception as e:
            logger.debug(f"Could not save applied items: {e}")

    def make_gui(self) -> "type[kvui.GameManager]":
        return P1UI

    async def server_auth(self, password_requested: bool = False) -> None:
        if not self.auth:
            await self.get_username()

        await super().server_auth(password_requested)

        await self.send_connect()

    def on_package(self, cmd: str, args: dict) -> None:
        if self.debug_mode:
            logger.info(f"[DEBUG] on_package cmd={cmd}")
        super().on_package(cmd, args)
        if cmd == "Connected":
            self.slot_data = args.get("slot_data", {})
            if not getattr(self, "seed_name", None):
                self.seed_name = args.get("seed_name", "unknown")
            if self.debug_mode:
                logger.info(f"[DEBUG] slot_data reçu: {self.slot_data}")
            self.pikmin_items_applied = {}  # reset before loading with correct key
            self.pikmin_dyn_pending = {"red": 0, "yellow": 0, "blue": 0}
            self.load_applied()
            self.needs_location_scout = True
            # Register for hints notifications
            self.stored_data_notification_keys.add(f"_read_hints_{self.team}_{self.slot}")
        elif cmd == "LocationInfo":
            count = len(args.get("locations", []))
            if self.debug_mode:
                logger.info(f"[DEBUG] Received LocationInfo with {count} locations")
            for item in args["locations"]:
                loc_id = item.location
                try:
                    item_name = self.item_names.lookup_in_slot(item.item, item.player)
                except Exception:
                    item_name = str(item.item)
                entry = {
                    "item_name": item_name,
                    "player":    item.player,
                    "flags":     item.flags if hasattr(item, "flags") else 0,
                }
                self.scouted_locations[loc_id] = entry
                self.all_locations_scouted[loc_id] = entry
            self.scout_received = True
            if self.debug_mode:
                logger.info(f"[DEBUG] Scouted {len(self.scouted_locations)} locations total")

        elif cmd == "SetReply":
            if args.get("key") == f"_read_hints_{self.team}_{self.slot}":
                hints = args.get("value", [])
                if self.debug_mode:
                    logger.info(f"[DEBUG] Received hints via SetReply: {len(hints)} hints")
                for hint in hints:
                    loc_id = hint.get("location")
                    if loc_id:
                        self.server_hints[loc_id] = hint
                if self.debug_mode:
                    logger.info(f"[DEBUG] Server hints total: {len(self.server_hints)}")

        elif cmd == "ReceivedHints":
            if self.debug_mode:
                logger.info(f"[DEBUG] ReceivedHints: {len(args.get('hints', []))} hints")
            for hint in args.get("hints", []):
                loc_id = hint.get("location")
                if loc_id:
                    self.server_hints[loc_id] = hint
            if self.debug_mode:
                logger.info(f"[DEBUG] Server hints total: {len(self.server_hints)}")


async def handle_pikmin_items(ctx: P1Context, game: Game) -> None:
    """Apply received Pikmin bonus items.

    The DOL stub stores r29 (onion base) per color to ONION_BASE_ADDRS.
    Client computes dyn_addr = base + 0x042C and writes pikmin there.
    Also writes to ONION_PERSISTENT_ADDRS to survive day transitions.
    """
    if game not in ONION_BASE_ADDRS:
        return

    base_addrs       = ONION_BASE_ADDRS[game]
    persistent_addrs = ONION_PERSISTENT_ADDRS[game]

    id_to_pikmin: dict[int, tuple[str, int]] = {
        FILLER_ITEMS[name]: PIKMIN_BONUS_ITEMS[name]
        for name in PIKMIN_BONUS_ITEMS
        if name in FILLER_ITEMS
    }

    def read_u32(addr: int) -> int:
        try:
            return int.from_bytes(dme.read_bytes(addr, 4), "big")
        except Exception:
            return 0

    def write_u32(addr: int, value: int) -> None:
        try:
            dme.write_bytes(addr, value.to_bytes(4, "big"))
        except Exception as e:
            logger.debug(f"Error writing to 0x{addr:08x}: {e}")

    def read_u16(addr: int) -> int:
        try:
            return int.from_bytes(dme.read_bytes(addr, 2), "big")
        except Exception:
            return 0

    def write_u16(addr: int, value: int) -> None:
        try:
            dme.write_bytes(addr, (value & 0xFFFF).to_bytes(2, "big"))
        except Exception as e:
            logger.debug(f"Error writing u16 to 0x{addr:08x}: {e}")

    # Apply pending DYN amounts for colors whose base is now known
    if not hasattr(ctx, "pikmin_dyn_pending"):
        ctx.pikmin_dyn_pending = {"red": 0, "yellow": 0, "blue": 0}

    for color in ["red", "yellow", "blue"]:
        pending = ctx.pikmin_dyn_pending.get(color, 0)
        if pending > 0:
            base = read_u32(base_addrs[color])
            if base and base > 0x80000000:
                dyn_addr = base + ONION_DYN_OFFSET
                old_dyn = read_u32(dyn_addr)
                new_dyn = old_dyn + pending
                write_u32(dyn_addr, new_dyn)
                ctx.pikmin_dyn_pending[color] = 0
                if ctx.debug_mode:
                    logger.info(f"[DEBUG] DYN PENDING flush {color} +{pending} : {old_dyn} -> {new_dyn}")

    def add_pikmin(color: str, amount: int) -> None:
        base = read_u32(base_addrs[color])
        if base and base > 0x80000000:
            dyn_addr = base + ONION_DYN_OFFSET
            old_dyn = read_u32(dyn_addr)
            new_dyn = old_dyn + amount
            write_u32(dyn_addr, new_dyn)
            if ctx.debug_mode:
                logger.info(f"[DEBUG] DYN   0x{dyn_addr:08x} : {old_dyn} -> {new_dyn} (base=0x{base:08x}, color={color})")
        else:
            ctx.pikmin_dyn_pending[color] = ctx.pikmin_dyn_pending.get(color, 0) + amount
            if ctx.debug_mode:
                logger.info(f"[DEBUG] DYN   PENDING {color} +{amount} (base invalid)")

        pers_addr = persistent_addrs[color]
        old_pers = read_u16(pers_addr)
        new_pers = old_pers + amount
        write_u16(pers_addr, new_pers)
        if ctx.debug_mode:
            logger.info(f"[DEBUG] PERS  0x{pers_addr:08x} : {old_pers} -> {new_pers} (color={color})")

    for item in ctx.items_received:
        item_id = item.item
        if item_id not in id_to_pikmin:
            continue

        color, count = id_to_pikmin[item_id]
        total_received = sum(1 for i in ctx.items_received if i.item == item_id)
        already_applied = ctx.pikmin_items_applied.get(item_id, 0)
        to_apply = total_received - already_applied
        if to_apply <= 0:
            continue

        bonus = count * to_apply
        if ctx.debug_mode:
            logger.info(f"[DEBUG] Item  {color} +{bonus} (item_id={item_id})")
        add_pikmin(color, bonus)

        ctx.pikmin_items_applied[item_id] = total_received

    ctx.save_applied()


async def handle_parts(ctx: P1Context, game: Game):
    for name, data in ALL_PARTS.items():
        # check locations if something got collected
        read = dme.read_byte(data.memory_address[game])

        # freshly collected
        if read == data.collected_byte and data.ap_id not in ctx.checked_locations:
            ctx.locations_checked.add(data.ap_id)
            await ctx.check_locations([data.ap_id])


async def handle_pikmin_locations(ctx: P1Context, game: Game):
    """Handle Pikmin collection location checking"""
    try:
        if game not in PIKMIN_ADDRESSES:
            return

        addresses = PIKMIN_ADDRESSES[game]

        # Read current Pikmin counts
        red_count    = dme.read_byte(addresses["red"])
        yellow_count = dme.read_byte(addresses["yellow"])
        blue_count   = dme.read_byte(addresses["blue"])

        # Only act if counts have changed since last tick
        if (red_count == ctx.last_red_count
                and yellow_count == ctx.last_yellow_count
                and blue_count == ctx.last_blue_count):
            return

        ctx.last_red_count    = red_count
        ctx.last_yellow_count = yellow_count
        ctx.last_blue_count   = blue_count

        current_counts = {
            "red":    red_count,
            "yellow": yellow_count,
            "blue":   blue_count,
        }

        # Build reverse map once: ap_id -> (color, threshold)
        id_to_pikmin: dict[int, tuple[str, int]] = {}
        for loc_name, loc_id in PIKMIN_LOCATIONS_MAP.items():
            parts = loc_name.split(" Pikmin: ")
            if len(parts) == 2:
                id_to_pikmin[loc_id] = (parts[0].lower(), int(parts[1]))

        locations_to_check = []

        for loc_id in ctx.missing_locations:
            if loc_id not in id_to_pikmin:
                continue
            color, threshold = id_to_pikmin[loc_id]
            if current_counts[color] >= threshold:
                locations_to_check.append(loc_id)

        if locations_to_check:
            await ctx.check_locations(locations_to_check)

        ctx.pikmin_counts["red"]    = red_count
        ctx.pikmin_counts["yellow"] = yellow_count
        ctx.pikmin_counts["blue"]   = blue_count

    except Exception as e:
        logger.debug(f"Error handling Pikmin locations: {e}")


async def handle_areas(ctx: P1Context, game: Game):
    # Build set of valid ship part IDs for fast lookup
    ship_part_ids = {data.ap_id for data in ALL_PARTS.values()}

    # Count only real ship parts received
    ship_parts_count = sum(1 for item in ctx.items_received if item.item in ship_part_ids)

    total_required = 0

    if ship_parts_count >= 30:
        total_required = 25

        if not ctx.finished_game:
            await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            ctx.finished_game = True

    areas = 0b00001
    if ship_parts_count >= 1:
        areas += 0b00010
    if ship_parts_count >= 5:
        areas += 0b00100
    if ship_parts_count >= 12:
        areas += 0b01000
    if ship_parts_count >= 29:
        areas += 0b10000

    dme.write_byte(COUNT_TOTAL_PARTS[game], ship_parts_count)
    dme.write_byte(COUNT_REQUIRED_PARTS[game], total_required)
    dme.write_byte(UNLOCKED_AREAS[game], areas)


async def handle_day_cycle(ctx: P1Context, game: Game) -> None:
    """Manage the day counter based on the player's day cycle option."""
    slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
    mode  = slot_data.get("day_cycle_mode",  0)  # 0=normal, 1=custom_range, 2=fixed
    d_min = slot_data.get("day_cycle_min",   2)
    d_max = slot_data.get("day_cycle_max",  29)
    fixed = slot_data.get("day_cycle_fixed",  2)

    try:
        day = dme.read_byte(DAY_NUMBER[game])
    except Exception:
        return

    if ctx.debug_mode:
        import time as _time
        _now = _time.monotonic()
        if _now - ctx._last_day_debug_log >= 60.0:
            logger.info(f"[DEBUG] Day cycle: day={day} mode={mode}")
            ctx._last_day_debug_log = _now

    new_day = day

    if mode == 0:  # normal: force 2 if day is 1 or above 29
        if day == 1 or day > 29:
            new_day = 2

    elif mode == 1:  # custom range
        low  = max(2, min(d_min, d_max))
        high = max(low, d_max)
        if day < low:
            new_day = low
        elif day > high:
            new_day = low

    elif mode == 2:  # fixed — lock on fixed value
        new_day = max(2, min(fixed, 29))

    if new_day != day:
        try:
            dme.write_byte(DAY_NUMBER[game], new_day)
        except Exception:
            pass


def build_hint_bytes(ctx: P1Context, part_name: str, hint_mode: int) -> bytes:
    """Build the hint as raw bytes, using ESC (0x1B) as GC color code prefix."""
    loc_id = ALL_PARTS[part_name].ap_id

    if hint_mode == 1:  # item mode: show what this location contains
        info = ctx.scouted_locations.get(loc_id)
        if not info:
            return b""
        item_name = info["item_name"]
        player_id = info["player"]
        player_name = ctx.player_names.get(player_id, str(player_id))
        flags = info.get("flags", 0)

        if flags & 0b100:
            item_color = "ff0000ff"
        elif flags & 0b010:
            item_color = "00ffffff"
        elif flags & 0b001:
            item_color = "cc00ffff"
        else:
            item_color = "b4ffffff"

        text = (
            f"\x1BCC[ff0000ff]{part_name}\x1BCC[b4ffffff]\n"
            f"Contains: \x1BCC[{item_color}]{item_name}\x1BCC[b4ffffff]\n"
            f"For: \x1BCC[ff0000ff]{player_name}\x1BCC[b4ffffff]"
        )
        result = text.encode("ascii", errors="replace")
        if len(result) < SHIP_PART_TEXT_LENGTH:
            result += b"\x00" * (SHIP_PART_TEXT_LENGTH - len(result))
        return result

    elif hint_mode == 2:  # super radar mode
        slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
        hints = slot_data.get("hints", {})
        hint_data = hints.get(part_name)

        if ctx.debug_mode:
            logger.info(f"[DEBUG] Super Radar - part: {part_name}, hints count: {len(hints)}, hint_data: {hint_data}")

        if hint_data:
            item_name   = hint_data.get("Item", "Unknown")
            location    = hint_data.get("Location", "Unknown")
            send_player = hint_data.get("Send Player", "Unknown")
            hint_class  = hint_data.get("Class", "Other")

            if ctx.debug_mode:
                logger.info(f"[DEBUG] Super Radar - Item: {item_name}, Location: {location}, SendPlayer: {send_player}, Class: {hint_class}")

            if hint_class == "Prog":
                item_color = "cc00ffff"
            elif hint_class == "Trap":
                item_color = "ff0000ff"
            else:
                item_color = "00ffffff"

            text = (
                f"\x1BCC[ff0000ff]{part_name}\x1BCC[b4ffffff]\n"
                f"Your Ship Part is at \x1BCC[ff0000ff]{location}\x1BCC[b4ffffff] in \x1BCC[ff0000ff]{send_player}\x1BCC[b4ffffff]"
            )
        else:
            if ctx.debug_mode:
                logger.info(f"[DEBUG] Super Radar - No hint data found for {part_name}")
            text = (
                f"\x1BCC[cc00ff]{part_name}\x1BCC[b4ffffff]\n"
                f"\x1BCC[00ffffff]No hint data"
            )

        result = text.encode("ascii", errors="replace")
        if len(result) < SHIP_PART_TEXT_LENGTH:
            result += b"\x00" * (SHIP_PART_TEXT_LENGTH - len(result))
        return result

    elif hint_mode == 3:  # both mode: show item content AND super radar info
        slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
        hints = slot_data.get("hints", {})
        radar_hint_key = f"{part_name}_radar"

        info = ctx.scouted_locations.get(loc_id)
        radar_hint_data = hints.get(radar_hint_key)
        if not radar_hint_data:
            radar_hint_data = hints.get(part_name)

        if not info or not radar_hint_data:
            if ctx.debug_mode:
                logger.info(f"[DEBUG] Both - Missing data: info={bool(info)}, radar_hint_data={bool(radar_hint_data)}")
            return b""

        item_name   = info["item_name"]
        player_id   = info["player"]
        player_name = ctx.player_names.get(player_id, str(player_id))
        flags       = info.get("flags", 0)

        if flags & 0b100:
            item_color = "ff0000ff"
        elif flags & 0b010:
            item_color = "00ffffff"
        elif flags & 0b001:
            item_color = "cc00ffff"
        else:
            item_color = "b4ffffff"

        location    = radar_hint_data.get("Location", "Unknown")
        send_player = radar_hint_data.get("Send Player", "Unknown")

        text = (
            f"\x1BCC[ff0000ff]{part_name}\x1BCC[b4ffffff]\n"
            f"Contains: \x1BCC[{item_color}]{item_name}\x1BCC[b4ffffff]\n"
            f"For: \x1BCC[ff0000ff]{player_name}\x1BCC[b4ffffff]\n"
            f"\nYour Ship Part is at:\n\x1BCC[ff0000ff]{location}\x1BCC[b4ffffff]\n"
            f"in \x1BCC[ff0000ff]{send_player}\x1BCC[b4ffffff]"
        )
        if ctx.debug_mode:
            logger.info(f"[DEBUG] Both hint text length: {len(text)}")
        result = text.encode("ascii", errors="replace")
        if len(result) < SHIP_PART_TEXT_LENGTH:
            result += b"\x00" * (SHIP_PART_TEXT_LENGTH - len(result))
        return result

    return b""


async def handle_ship_part_hints(ctx: P1Context, game: Game) -> None:
    """Detect which ship part text is displayed and replace it with an Archipelago hint.
    Re-applies the hint every tick as long as the original game text is still visible,
    so the game cannot permanently overwrite our text."""
    # Only PAL supported for now (NTSC-U address TBD)
    if game != b"GPIP01":
        return

    slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
    hint_mode = slot_data.get("ship_part_hint_mode", 0)
    if hint_mode == 0:
        return

    hint_mode_is_both = hint_mode == 3

    try:
        raw = dme.read_bytes(SHIP_PART_TEXT_ADDR, SHIP_PART_TEXT_LENGTH)
    except Exception:
        return

    if not any(raw):
        ctx.last_hint_shown = ""
        ctx.last_hint_bytes = b""
        return

    first_newline = raw.find(b"\n")
    first_line = raw[:first_newline] if first_newline != -1 else raw
    detected_part = None
    for part_name in ALL_PARTS:
        if part_name.encode("ascii") in first_line:
            detected_part = part_name
            break

    if not detected_part:
        if ctx.last_hint_shown and ctx.last_hint_bytes:
            part_bytes = ctx.last_hint_shown.encode("ascii")
            if part_bytes in raw:
                if hint_mode_is_both:
                    elapsed = time.monotonic() - ctx.hint_both_last_toggle
                    if elapsed >= BOTH_MODE_TOGGLE_INTERVAL:
                        ctx.hint_both_toggle = not ctx.hint_both_toggle
                        ctx.hint_both_last_toggle = time.monotonic()
                        current_hint_mode = 1 if not ctx.hint_both_toggle else 2
                        new_hint_bytes = build_hint_bytes(ctx, ctx.last_hint_shown, current_hint_mode)
                        if new_hint_bytes:
                            ctx.last_hint_bytes = new_hint_bytes
                            if ctx.debug_mode:
                                logger.info(f"[DEBUG] Both mode toggle: mode={current_hint_mode}")
                            try:
                                dme.write_bytes(SHIP_PART_TEXT_ADDR, ctx.last_hint_bytes)
                            except Exception as e:
                                logger.debug(f"Error re-applying hint: {e}")
                else:
                    try:
                        dme.write_bytes(SHIP_PART_TEXT_ADDR, ctx.last_hint_bytes)
                    except Exception as e:
                        logger.debug(f"Error re-applying hint: {e}")
        return

    if detected_part != ctx.last_hint_shown:
        loc_id = ALL_PARTS[detected_part].ap_id
        ctx.hint_both_toggle = False
        ctx.hint_both_last_toggle = time.monotonic()

        if hint_mode == 1 or hint_mode_is_both:
            item_hint_key = f"{detected_part}_item" if hint_mode_is_both else detected_part
            if item_hint_key not in ctx.created_hints:
                ctx.created_hints.add(item_hint_key)
                await ctx.send_msgs([{
                    "cmd": "CreateHints",
                    "locations": [loc_id],
                    "player": ctx.slot,
                }])
                if ctx.debug_mode:
                    logger.info(f"[DEBUG] CreateHints sent for {detected_part} (loc_id={loc_id})")

        if hint_mode == 2 or hint_mode_is_both:
            slot_hints: dict = (ctx.slot_data or {}).get("hints", {})
            radar_hint_key = f"{detected_part}_radar" if hint_mode_is_both else detected_part
            hint_data = slot_hints.get(radar_hint_key)
            if not hint_data:
                hint_data = slot_hints.get(detected_part)
            if hint_data and radar_hint_key not in ctx.created_hints:
                ctx.created_hints.add(radar_hint_key)
                try:
                    target_loc_id = int(hint_data.get("Location ID", 0))
                    target_player = int(hint_data.get("Send Player ID", ctx.slot))
                except (ValueError, TypeError):
                    target_loc_id = 0
                    target_player = ctx.slot
                if target_loc_id:
                    await ctx.send_msgs([{
                        "cmd": "CreateHints",
                        "locations": [target_loc_id],
                        "player": target_player,
                    }])
                    if ctx.debug_mode:
                        logger.info(f"[DEBUG] Super Radar CreateHints for {detected_part} "
                                    f"(loc_id={target_loc_id}, player={target_player})")

        current_hint_mode = hint_mode
        hint_bytes = build_hint_bytes(ctx, detected_part, current_hint_mode)
        if not hint_bytes:
            if ctx.debug_mode:
                logger.info(f"[DEBUG] No hint text for {detected_part} (scouted={len(ctx.scouted_locations)})")
            return

        ctx.last_hint_shown = detected_part
        ctx.last_hint_bytes = hint_bytes

        if ctx.debug_mode:
            logger.info(f"[DEBUG] Writing hint for {detected_part} (mode={current_hint_mode})")

        try:
            dme.write_bytes(SHIP_PART_TEXT_ADDR, hint_bytes)
        except Exception as e:
            logger.debug(f"Error writing hint text: {e}")

    else:
        if ctx.last_hint_bytes:
            try:
                dme.write_bytes(SHIP_PART_TEXT_ADDR, ctx.last_hint_bytes)
            except Exception as e:
                logger.debug(f"Error re-applying hint: {e}")
        elif ctx.scouted_locations or ctx.all_locations_scouted:
            hint_bytes = build_hint_bytes(ctx, detected_part, hint_mode)
            if hint_bytes:
                ctx.last_hint_bytes = hint_bytes
                if ctx.debug_mode:
                    logger.info(f"[DEBUG] Late hint build for {detected_part}")
                try:
                    dme.write_bytes(SHIP_PART_TEXT_ADDR, hint_bytes)
                except Exception as e:
                    logger.debug(f"Error writing late hint: {e}")


async def dolphin_loop(ctx: P1Context):
    game_version = None

    while not ctx.exit_event.is_set():
        try:
            await asyncio.wait_for(ctx.watcher_event.wait(), 1.0)
        except asyncio.TimeoutError:
            pass

        ctx.watcher_event.clear()

        if ctx.needs_location_scout:
            ctx.needs_location_scout = False
            ctx.scout_sent = True
            ctx.scout_sent_time = time.monotonic()
            ctx.scout_received = False

            all_locations = list(ALL_LOCATIONS.values())

            slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
            hint_mode_val = slot_data.get("ship_part_hint_mode", 0)
            if hint_mode_val == 2 or hint_mode_val == 3:
                all_server_locs = set(ctx.checked_locations) | set(ctx.missing_locations)
                all_locations = list(all_server_locs)
                logger.info(f"[Super Radar] Sending LocationScouts for {len(all_locations)} locations")

            logger.info(f"[DEBUG] Sending LocationScouts with {len(all_locations)} locations")
            await ctx.send_msgs([{
                "cmd": "LocationScouts",
                "locations": all_locations,
                "create_as_hint": 0,
            }])

        if ctx.scout_sent and not ctx.scout_received:
            elapsed = time.monotonic() - ctx.scout_sent_time
            if elapsed >= SCOUT_RETRY_INTERVAL:
                ctx.scout_sent_time = time.monotonic()
                logger.info(f"[DEBUG] Retrying LocationScouts (no response after {elapsed:.0f}s, "
                            f"scouted={len(ctx.scouted_locations)})")
                await ctx.send_msgs([{
                    "cmd": "LocationScouts",
                    "locations": list(ALL_LOCATIONS.values()),
                    "create_as_hint": 0,
                }])

        try:
            if not dme.is_hooked():
                dme.hook()
            if not dme.is_hooked():
                ctx.dolphin_status_text = "Disconnected - Hook Failed"
                continue
            else:
                game = dme.read_bytes(0x80000000, 6)

                # Build expected patched Game ID from slot_data
                slot_data = getattr(ctx, "slot_data", {}) or {}
                suffix = slot_data.get("game_id_suffix", "")

                if not suffix:
                    # Not yet connected to AP server — accept any P1P patched ISO
                    if not game.startswith(b"P1P"):
                        ctx.dolphin_status_text = "Connected - Wrong Game (patch your ISO first)"
                        continue
                    game_version = b"GPIP01"
                else:
                    expected_patched_id = b"P1P" + suffix.encode("ascii")
                    if game != expected_patched_id:
                        ctx.dolphin_status_text = f"Connected - Wrong Game (expected {expected_patched_id.decode()})"
                        continue
                    game_version = b"GPIP01"

                ctx.dolphin_status_text = f"Connected - {game.decode()}"

                if game == b"GPIE01":
                    _now = time.monotonic()
                    if _now - ctx._last_ntsc_warning >= 60.0:
                        logger.warning(
                            "Warning : You use Pikmin NTSC This version does not completely support "
                            "the risk of bugs and crashes is very high"
                        )
                        ctx._last_ntsc_warning = _now
        except Exception as e:
            logger.error(e)
            logger.info("Trying to reconnect to Dolphin...")
            ctx.dolphin_status_text = "??? - Exception Occured"
            dme.un_hook()
            continue

        await handle_parts(ctx, game_version)
        await handle_pikmin_locations(ctx, game_version)
        await handle_pikmin_items(ctx, game_version)
        await handle_day_cycle(ctx, game_version)
        await handle_ship_part_hints(ctx, game_version)
        await handle_areas(ctx, game_version)
        # TODO if "DeathLink" in ctx.tags: handle that


def run_client(*args) -> None:
    # args may contain the path to a .appik1 file when launched via double-click
    appik1_path = args[0] if args and isinstance(args[0], str) and args[0].endswith(".appik1") else None

    # Patch the ISO if a valid .appik1 was provided
    if appik1_path and os.path.isfile(appik1_path):
        _handle_patch(appik1_path)

    async def main() -> None:
        parser = get_base_parser()
        parser.add_argument("appik1_file", default="", type=str, nargs="?",
                            help="Path to a .appik1 patch file")
        parsed = parser.parse_args()

        # Also handle patch if passed as CLI argument
        if parsed.appik1_file and not appik1_path:
            _handle_patch(parsed.appik1_file)

        ctx = P1Context(parsed.connect, parsed.password)
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")

        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()

        loop_task = asyncio.create_task(dolphin_loop(ctx), name="game loop")

        await loop_task
        await ctx.exit_event.wait()
        await ctx.shutdown()

    Utils.init_logging("PikminClient")

    import colorama
    colorama.init()
    asyncio.run(main())
    colorama.deinit()


def _handle_patch(appik1_path: str) -> None:
    """Patch a copy of the user's Pikmin 1 PAL ISO when a .appik1 file is opened."""
    from .P1Rom import verify_iso, patch_iso, InvalidISOError
    from settings import get_settings
    import shutil

    options = get_settings()
    iso_path = options.get("pikmin_options", {}).get("iso_file", "")
    if iso_path and not os.path.isfile(iso_path):
        iso_path = Utils.user_path(iso_path)

    # If no ISO configured or file doesn't exist, open a file picker
    if not iso_path or not os.path.isfile(iso_path):
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.wm_attributes("-topmost", True)
            iso_path = filedialog.askopenfilename(
                title="Select your clean Pikmin 1 PAL ISO (GP1P01)",
                filetypes=[("GameCube ISO", "*.iso *.gcm"), ("All files", "*.*")],
            )
            root.destroy()
        except Exception as e:
            logger.error(f"[Pikmin] Could not open file dialog: {e}")
            iso_path = ""

        if not iso_path:
            Utils.messagebox(
                "Cannot Patch Pikmin 1",
                "No ISO selected. Please select your clean Pikmin 1 PAL ISO (GP1P01).",
                error=True,
            )
            return

        # Save the path to host.yml for next time
        try:
            if "pikmin_options" not in options:
                options["pikmin_options"] = {}
            options["pikmin_options"]["iso_file"] = iso_path
            options.save()
            logger.info(f"[Pikmin] Saved ISO path to host.yml: {iso_path}")
        except Exception as e:
            logger.warning(f"[Pikmin] Could not save ISO path to host.yml: {e}")

    # Build output path: same folder as the .appik1, same name as ISO
    patch_dir = os.path.dirname(os.path.abspath(appik1_path))
    patch_basename = os.path.splitext(os.path.basename(appik1_path))[0]
    iso_ext = os.path.splitext(iso_path)[1]
    output_iso = os.path.join(patch_dir, patch_basename + iso_ext)

    # Copy the clean ISO to the output path
    try:
        shutil.copy2(iso_path, output_iso)
        logger.info(f"[Pikmin] Copied clean ISO to: {output_iso}")
    except Exception as e:
        Utils.messagebox("Cannot Patch Pikmin 1", f"Could not copy ISO:\n{e}", error=True)
        return

    # Read seed from .appik1
    seed = ""
    try:
        import zipfile, json
        with zipfile.ZipFile(appik1_path, "r") as zf:
            with zf.open("patch.appik1") as f:
                data = json.load(f)
                seed = str(data.get("Seed", ""))
    except Exception as e:
        logger.warning(f"[Pikmin] Could not read seed from .appik1: {e}")

    # Verify and patch the copy
    try:
        verify_iso(output_iso)
        patch_iso(output_iso, seed=seed)
        logger.info(f"[Pikmin] ISO patched successfully: {output_iso}")
        Utils.messagebox(
            "Pikmin 1 Patched",
            f"Patched ISO created successfully!\n{output_iso}"
        )
    except InvalidISOError as e:
        logger.error(f"[Pikmin] ISO verification failed: {e}")
        try:
            os.remove(output_iso)
        except Exception:
            pass
        Utils.messagebox("Cannot Patch Pikmin 1", str(e), error=True)
    except Exception as e:
        logger.error(f"[Pikmin] Unexpected error during patching: {e}")
        try:
            os.remove(output_iso)
        except Exception:
            pass
        Utils.messagebox("Cannot Patch Pikmin 1", f"Unexpected error:\n{e}", error=True)


if __name__ == "__main__":
    run_client()