import asyncio
from typing import TYPE_CHECKING, Optional

import dolphin_memory_engine as dme

import Utils
from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus
from .P1UI import P1UI
from .P1Data import *

if TYPE_CHECKING:
    import kvui

UNLOCKED_AREAS: MemoryAddress = mem(0x803A2803, 0x8039D983)  # byte
COUNT_TOTAL_PARTS: MemoryAddress = mem(0x812427FF, 0x81249DE7)  # byte
COUNT_REQUIRED_PARTS: MemoryAddress = mem(0x81242803, 0x81249DEB)  # byte
TIME_HOURS: MemoryAddress = mem(0x803A2930, 0x803A2930)  # int, 7=morning, >=19=end of day
TIME_HOURS: MemoryAddress = mem(0x803A2930, 0x803A2930)  # int, 7=morning, >=19=end of day


# Pikmin memory addresses for PAL version
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

# Onion Pikmin count addresses - short (2 bytes BE), persistent across days
# PAL confirmed via RAM Watch (typeIndex=1)
ONION_ADDRESSES_PAL = {
    "red":    0x803D6D26,
    "yellow": 0x803D6C8A,
    "blue":   0x803D6C72,
}

ONION_ADDRESSES_NTSC_U = {
    "red":    0x803D1EA6,  # TODO: verify NTSC-U
    "yellow": 0x803D1E0A,
    "blue":   0x803D1DF2,
}

PIKMIN_ADDRESSES = {
    b"GPIP01": PIKMIN_ADDRESSES_PAL,
    b"GPIE01": PIKMIN_ADDRESSES_NTSC_U,
}

ONION_ADDRESSES = {
    b"GPIP01": ONION_ADDRESSES_PAL,
    b"GPIE01": ONION_ADDRESSES_NTSC_U,
}

# Addresses per color for adding Pikmin bonus
# Format: {"color": [(address, zone_filter)]}
# zone_filter: None = always write, string = only write if current zone matches
PIKMIN_BONUS_ADDR_PAL: dict[str, list[tuple[int, str | None]]] = {
    "red": [
        (0x803D6C7E, None),                                  # persistent, always write
        (0x810B3C6E, "courses/practice/practice.mod"),       # Crash Site
        (0x810B3EB6, "courses/practice/practice.mod"),       # Crash Site (OFF - post-intro)
        (0x8110E20E, "courses/stage1/forest.mod"),           # Forest of Hope
        (0x8110EDD6, "courses/stage2/cave.mod"),             # Forest Navel
        (0x811593DE, "courses/stage3/yakusima.mod"),         # Distant Spring
        (0x810D4D6E, "courses/laststage/garden.mod"),        # Final Trial
    ],
    "yellow": [
        (0x803D6C8A, None),                                  # persistent, always write
        (0x810B48FE, "courses/practice/practice.mod"),       # Crash Site
        (0x8110CC66, "courses/stage1/forest.mod"),           # Forest of Hope
        (0x811103C6, "courses/stage1/forest.mod"),           # Forest of Hope (OFF)
        (0x8110FA66, "courses/stage2/cave.mod"),             # Forest Navel
        (0x8115A06E, "courses/stage3/yakusima.mod"),         # Distant Spring
        (0x810D59FE, "courses/laststage/garden.mod"),        # Final Trial
    ],
    "blue": [
        (0x803D6C72, None),                                  # persistent, always write
        (0x810B3C4E, "courses/practice/practice.mod"),       # Crash Site
        (0x8110C98E, "courses/stage1/forest.mod"),           # Forest of Hope
        (0x8110E146, "courses/stage2/cave.mod"),             # Forest Navel
        (0x8111255E, "courses/stage2/cave.mod"),             # Forest Navel (OFF)
        (0x8115874E, "courses/stage3/yakusima.mod"),         # Distant Spring
        (0x810D40DE, "courses/laststage/garden.mod"),        # Final Trial
    ],
}

# Address containing the current zone name string (ASCII, null-terminated)
CURRENT_ZONE_ADDR: MemoryAddress = mem(0x803A2A50, 0x803A2A50)
CURRENT_ZONE_LENGTH = 35  # max length to read

PIKMIN_BONUS_ADDR = {
    b"GPIP01": PIKMIN_BONUS_ADDR_PAL,
}

# ONION_FLAGS: MemoryAddress = mem(0x81242804, 0x81242804)  # byte bitmask PAL
ONION_FLAG_RED    = 18
ONION_FLAG_YELLOW = 36
ONION_FLAG_BLUE   = 9
# COUNT_LOCAL_PARTS_2: MemoryAddress = mem(0x81242808, 0x81249DF0)  # byte
# COUNT_LOCAL_PARTS_3: MemoryAddress = mem(0x81242809, 0x81249DF1)  # byte
# COUNT_LOCAL_PARTS_4: MemoryAddress = mem(0x8124280A, 0x81249DF2)  # byte
# COUNT_LOCAL_PARTS_5: MemoryAddress = mem(0x8124280B, 0x81249DF3)  # byte
#
# TIME_HOURS: MemoryAddress = mem(0x803A2930)  # word, daytime is 7-18, day ends >= 19, night mode (moon icon) <= 6
# TIME_MINUTES: MemoryAddress = mem(0x803A2924)  # word, explore how exactly this works


class P1CommandProcessor(ClientCommandProcessor):
    def __init__(self, ctx: CommonContext):
        super().__init__(ctx)

    def _cmd_debug(self) -> bool:
        """Toggle debug logging for Pikmin client."""
        self.ctx.debug_mode = not getattr(self.ctx, "debug_mode", False)
        state = "ON" if self.ctx.debug_mode else "OFF"
        logger.info(f"Pikmin debug mode: {state}")
        return True

    def _cmd_crash(self) -> bool:
        """Re-apply all received Pikmin bonus items and re-check all collected ship part locations.
        Use this if the game crashed and you lost progress."""
        # Reset applied items so all bonuses get re-applied
        self.ctx.pikmin_items_applied = {}
        self.ctx.pending_zone_bonus = {"red": 0, "yellow": 0, "blue": 0}
        self.ctx.pending_onion_unlock_bonus = {"red": 0, "yellow": 0, "blue": 0}
        self.ctx.zone_addr_active = {"red": {}, "yellow": {}, "blue": {}}
        self.ctx.zone_addr_last_vals = {"red": {}, "yellow": {}, "blue": {}}
        self.ctx.save_applied()

        # Remove ship part location IDs from checked_locations so they get re-checked
        ship_part_location_ids = {data.ap_id for data in ALL_PARTS.values()}
        self.ctx.locations_checked -= ship_part_location_ids

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
        # Pending zone bonus per color waiting for Onion to be unlocked
        self.pending_onion_unlock_bonus: dict[str, int] = {"red": 0, "yellow": 0, "blue": 0}
        # Last known Onion unlock state to detect when it changes
        self.last_onion_flags: int = -1
        # Track last known zone address values per color to detect when they become active
        # A zone address is "active" when its value decreases (player took Pikmin from Onion)
        self.zone_addr_last_vals: dict[str, dict[int, int]] = {"red": {}, "yellow": {}, "blue": {}}
        self.zone_addr_active: dict[str, dict[int, bool]] = {"red": {}, "yellow": {}, "blue": {}}
        # Pending bonus per color waiting for zone addresses to become active
        self.pending_zone_bonus: dict[str, int] = {"red": 0, "yellow": 0, "blue": 0}

    def _save_key(self) -> str:
        seed = getattr(self, "seed_name", None) or "unknown"
        return f"applied_{self.auth}_{seed}"

    def load_applied(self) -> None:
        try:
            data = Utils.persistent_load().get("pikmin", {}).get(self._save_key(), {})
            self.pikmin_items_applied = {int(k): v for k, v in data.items()}
            logger.info(f"Loaded {len(self.pikmin_items_applied)} applied Pikmin items")
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

    async def on_package(self, cmd: str, args: dict) -> None:
        await super().on_package(cmd, args)
        if cmd == "Connected":
            self.load_applied()


async def handle_pikmin_items(ctx: P1Context, game: Game) -> None:
    """Apply received Pikmin bonus items immediately.
    Persistent address always written, real-time address only if zone matches.
    At day start, verifies zone addresses against persistent value to avoid writing to wrong addresses."""
    if game not in PIKMIN_BONUS_ADDR:
        return

    bonus_addrs = PIKMIN_BONUS_ADDR[game]

    # Read current zone name
    try:
        zone_bytes = dme.read_bytes(CURRENT_ZONE_ADDR[game], CURRENT_ZONE_LENGTH)
        current_zone = zone_bytes.split(b'\x00')[0].decode("ascii", errors="replace")
    except Exception:
        current_zone = ""

    # Detect day start (hour == 7 after being >= 19)
    try:
        current_hour = dme.read_word(TIME_HOURS[game])
    except Exception:
        current_hour = -1

    day_just_started = ctx.last_hour >= 19 and current_hour == 7
    if ctx.last_hour == -1:
        ctx.last_hour = current_hour
    else:
        ctx.last_hour = current_hour

    # Build ID -> (color, count) map
    id_to_pikmin: dict[int, tuple[str, int]] = {
        FILLER_ITEMS[name]: PIKMIN_BONUS_ITEMS[name]
        for name in PIKMIN_BONUS_ITEMS
        if name in FILLER_ITEMS
    }

    def get_persistent_val(color: str) -> int:
        """Read the persistent (always-valid) address value for a color."""
        addrs = bonus_addrs.get(color, [])
        persistent_addr = next((addr for addr, zone in addrs if zone is None), None)
        if persistent_addr:
            try:
                return int.from_bytes(dme.read_bytes(persistent_addr, 2), "big")
            except Exception:
                pass
        return -1

    def update_zone_activity(color: str) -> None:
        """
        Mark a zone address as active if:
        1. Its value matches the persistent save value (immediate activation), OR
        2. Its value has changed since last tick (player interacted with Onion)
        """
        addrs = bonus_addrs.get(color, [])
        # Get persistent value as reference
        persistent_addr = next((addr for addr, zone in addrs if zone is None), None)
        persistent_val = -1
        if persistent_addr:
            try:
                persistent_val = int.from_bytes(dme.read_bytes(persistent_addr, 2), "big")
            except Exception:
                pass

        for addr, zone_filter in addrs:
            if zone_filter is None or zone_filter != current_zone:
                continue
            try:
                val = int.from_bytes(dme.read_bytes(addr, 2), "big")
                last = ctx.zone_addr_last_vals[color].get(addr, -1)

                # Activate immediately if value matches persistent save
                if persistent_val != -1 and val == persistent_val:
                    ctx.zone_addr_active[color][addr] = True
                # Also activate if value changed since last tick
                elif last != -1 and val != last:
                    ctx.zone_addr_active[color][addr] = True

                ctx.zone_addr_last_vals[color][addr] = val
            except Exception:
                pass

    # Read current Onion unlock flags
    onion_flag_map = {"red": ONION_FLAG_RED, "yellow": ONION_FLAG_YELLOW, "blue": ONION_FLAG_BLUE}
    try:
        current_onion_flags = dme.read_byte(ONION_FLAGS[game])
    except Exception:
        current_onion_flags = 0xFF  # assume all unlocked on error

    def onion_unlocked(color: str) -> bool:
        return bool(current_onion_flags & onion_flag_map.get(color, 0))

    def apply_bonus(color: str, bonus: int) -> bool:
        """
        Write bonus to persistent address always.
        Write to zone addresses only if Onion is unlocked AND address is confirmed active.
        If Onion not yet unlocked, queue for later.
        If no zone address is active yet, queue the bonus and return False.
        """
        addrs = bonus_addrs.get(color, [])
        if not addrs:
            return False

        zone_addrs = [(addr, zf) for addr, zf in addrs if zf is not None and zf == current_zone]
        any_active = any(ctx.zone_addr_active[color].get(addr, False) for addr, _ in zone_addrs)

        try:
            # Always write to persistent address
            for addr, zone_filter in addrs:
                if zone_filter is not None:
                    continue
                raw = dme.read_bytes(addr, 2)
                current_val = int.from_bytes(raw, "big")
                dme.write_bytes(addr, (current_val + bonus).to_bytes(2, "big"))

            if not zone_addrs:
                return True

            # If Onion not unlocked, queue for later
            if not onion_unlocked(color):
                ctx.pending_onion_unlock_bonus[color] += bonus
                if ctx.debug_mode:
                    logger.info(f"[DEBUG] {color} Onion not unlocked, queued {bonus} Pikmin")
                return True  # persistent was written, return True

            if not any_active:
                return False  # zone addresses exist but not active yet

            # Write to active zone addresses only
            for addr, _ in zone_addrs:
                if not ctx.zone_addr_active[color].get(addr, False):
                    continue
                raw = dme.read_bytes(addr, 2)
                current_val = int.from_bytes(raw, "big")
                dme.write_bytes(addr, (current_val + bonus).to_bytes(2, "big"))

            return True
        except Exception as e:
            logger.debug(f"Error applying Pikmin bonus: {e}")
            return False

    # Check if an Onion was just unlocked and apply pending bonus
    if ctx.last_onion_flags != -1 and current_onion_flags != ctx.last_onion_flags:
        for color, flag in onion_flag_map.items():
            was_locked = not bool(ctx.last_onion_flags & flag)
            now_unlocked = bool(current_onion_flags & flag)
            if was_locked and now_unlocked:
                amount = ctx.pending_onion_unlock_bonus[color]
                if amount > 0:
                    # Apply to zone addresses now that Onion is unlocked
                    zone_addrs = [(addr, zf) for addr, zf in bonus_addrs.get(color, [])
                                  if zf is not None and zf == current_zone]
                    for addr, _ in zone_addrs:
                        if ctx.zone_addr_active[color].get(addr, False):
                            try:
                                raw = dme.read_bytes(addr, 2)
                                current_val = int.from_bytes(raw, "big")
                                dme.write_bytes(addr, (current_val + amount).to_bytes(2, "big"))
                            except Exception as e:
                                logger.debug(f"Error applying unlock bonus: {e}")
                    ctx.pending_onion_unlock_bonus[color] = 0
                    logger.info(f"{color} Onion unlocked! Applied pending {amount} Pikmin to zone")
    ctx.last_onion_flags = current_onion_flags

    # Update zone activity tracking for all colors
    for color in ["red", "yellow", "blue"]:
        update_zone_activity(color)

    # Apply pending zone bonuses if addresses just became active
    for color, amount in list(ctx.pending_zone_bonus.items()):
        if amount <= 0:
            continue
        zone_addrs = [(addr, zf) for addr, zf in bonus_addrs.get(color, [])
                      if zf is not None and zf == current_zone]
        if any(ctx.zone_addr_active[color].get(addr, False) for addr, _ in zone_addrs):
            try:
                for addr, _ in zone_addrs:
                    if ctx.zone_addr_active[color].get(addr, False):
                        raw = dme.read_bytes(addr, 2)
                        current_val = int.from_bytes(raw, "big")
                        dme.write_bytes(addr, (current_val + amount).to_bytes(2, "big"))
                ctx.pending_zone_bonus[color] = 0
                if ctx.debug_mode:
                    logger.info(f"[DEBUG] Applied pending {amount} {color} Pikmin to zone")
            except Exception as e:
                logger.debug(f"Error applying pending zone bonus: {e}")

    # Apply bonus immediately for each newly received item
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
        zone_addrs_for_color = [(addr, zf) for addr, zf in bonus_addrs.get(color, [])
                                 if zf is not None and zf == current_zone]
        any_active_log = any(ctx.zone_addr_active[color].get(addr, False) for addr, _ in zone_addrs_for_color)
        if ctx.debug_mode:
            logger.info(f"[DEBUG] Received {bonus} {color} Pikmin | zone={current_zone} | zone_addrs={len(zone_addrs_for_color)} | any_active={any_active_log}")
        if apply_bonus(color, bonus):
            ctx.pikmin_items_applied[item_id] = total_received
            ctx.save_applied()
        else:
            ctx.pending_zone_bonus[color] += bonus
            ctx.pikmin_items_applied[item_id] = total_received
            ctx.save_applied()
            if ctx.debug_mode:
                logger.info(f"[DEBUG] Queued {bonus} {color} Pikmin for zone (not yet active)")




async def handle_parts(ctx: P1Context, game: Game):
    for name, data in ALL_PARTS.items():
        # check locations if something got collected
        read = dme.read_byte(data.memory_address[game])

        # freshly collected
        if read == data.collected_byte and data.ap_id not in ctx.checked_locations:
            ctx.locations_checked.add(data.ap_id)
            await ctx.check_locations([data.ap_id])

    # if ctx.locations_checked == ctx.checked_locations:
    # client and server data match -> it's safe to change memory
    # here we could do the following:
    # - put parts whose location we have checked but whose item we haven't received yet to 0 (should be safe)
    # - put parts whose item we have received but whose location we haven't checked yet to 3
    # the latter could be prone to TOCTOU errors where we read and check it at 0, then it gets collected ingame
    # and becomes 1/2, then we set it to 3, never noticing that it got collected (it can't ever get collected again)
    # currently doing neither so that parts on the ship == locations checked instead of items received or sth mixed
    # consider only updating the latter case (or both) in menus/paused once we can detect that


async def handle_pikmin_locations(ctx: P1Context, game: Game):
    """Handle Pikmin collection location checking"""
    try:
        if game not in PIKMIN_ADDRESSES:
            return

        addresses = PIKMIN_ADDRESSES[game]

        # Read current Pikmin counts
        red_count = dme.read_byte(addresses["red"])
        yellow_count = dme.read_byte(addresses["yellow"])
        blue_count = dme.read_byte(addresses["blue"])

        # Only act if counts have changed since last tick
        if (red_count == ctx.last_red_count
                and yellow_count == ctx.last_yellow_count
                and blue_count == ctx.last_blue_count):
            return

        ctx.last_red_count = red_count
        ctx.last_yellow_count = yellow_count
        ctx.last_blue_count = blue_count

        current_counts = {
            "red": red_count,
            "yellow": yellow_count,
            "blue": blue_count,
        }

        # Build reverse map once: ap_id -> (color, threshold)
        id_to_pikmin: dict[int, tuple[str, int]] = {}
        for loc_name, loc_id in PIKMIN_LOCATIONS_MAP.items():
            parts = loc_name.split(" Pikmin: ")
            if len(parts) == 2:
                id_to_pikmin[loc_id] = (parts[0].lower(), int(parts[1]))

        locations_to_check = []

        # Iterate ONLY over locations the SERVER registered for this player.
        # ctx.missing_locations is the authoritative list — it only contains IDs
        # actually created during generation (respecting the interval).
        # ctx.check_locations() internally skips already-checked locations.
        for loc_id in ctx.missing_locations:
            if loc_id not in id_to_pikmin:
                continue
            color, threshold = id_to_pikmin[loc_id]
            if current_counts[color] >= threshold:
                locations_to_check.append(loc_id)

        if locations_to_check:
            await ctx.check_locations(locations_to_check)

        # Update counts for UI/logging
        ctx.pikmin_counts["red"] = red_count
        ctx.pikmin_counts["yellow"] = yellow_count
        ctx.pikmin_counts["blue"] = blue_count

    except Exception as e:
        logger.debug(f"Error handling Pikmin locations: {e}")


async def handle_areas(ctx: P1Context, game: Game):
    # Build set of valid ship part IDs for fast lookup
    ship_part_ids = {data.ap_id for data in ALL_PARTS.values()}

    # Count only real ship parts received
    ship_parts_count = sum(1 for item in ctx.items_received if item.item in ship_part_ids)
    
    total_required = 0

    if ship_parts_count >= 30:  # lazy: this makes olimar succeed once all parts have been collected
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


async def dolphin_loop(ctx: P1Context):
    game_version = None

    while not ctx.exit_event.is_set():
        try:
            await asyncio.wait_for(ctx.watcher_event.wait(), 1.0)
        except asyncio.TimeoutError:
            pass

        ctx.watcher_event.clear()

        try:
            # could maybe just do the else branch and check for game there
            if not dme.is_hooked():
                dme.hook() # silently fails?
            if not dme.is_hooked():
                ctx.dolphin_status_text = "Disconnected - Hook Failed"
                continue
            else:
                game = dme.read_bytes(0x80000000, 6)
                if game not in [b"GPIP01", b"GPIE01"]:
                    ctx.dolphin_status_text = "Connected - Wrong Game"
                    continue

                game_version = game
                ctx.dolphin_status_text = f"Connected - {game.decode()}"
                # TODO preferably check that the game is in a save file too
        except Exception as e:
            logger.error(e)
            logger.info("Trying to reconnect to Dolphin...")
            ctx.dolphin_status_text = "??? - Exception Occured"
            dme.un_hook()
            continue

        await handle_parts(ctx, game_version)
        await handle_pikmin_locations(ctx, game_version)
        await handle_pikmin_items(ctx, game_version)
        await handle_areas(ctx, game_version)
        # TODO if "DeathLink" in ctx.tags: handle that


def run_client() -> None:
    async def main() -> None:
        parser = get_base_parser()
        args = parser.parse_args()

        ctx = P1Context(args.connect, args.password)
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


if __name__ == "__main__":
    run_client()