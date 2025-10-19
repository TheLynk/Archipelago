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

# Pikmin memory addresses for PAL version
PIKMIN_ADDRESSES_PAL = {
    "red": 0x803D6CF7,
    "yellow": 0x803D6CFB,
    "blue": 0x803D6CF3,
}

# TODO: Add NTSC-U and other versions
PIKMIN_ADDRESSES = {
    b"GPIP01": PIKMIN_ADDRESSES_PAL,  # PAL
    b"GPIE01": PIKMIN_ADDRESSES_PAL,  # NTSC-U (verify addresses)
}

# COUNT_LOCAL_PARTS_1: MemoryAddress = mem(0x81242807, 0x81249DEF)  # byte
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


class P1Context(CommonContext):
    command_processor = P1CommandProcessor
    game: str = "Pikmin"
    items_handling: int = 0b111

    def __init__(self, server_address: Optional[str], password: Optional[str]) -> None:
        super().__init__(server_address, password)
        self.dolphin_status_text = "Disconnected"
        
        # Track Pikmin counts for location checking
        self.pikmin_counts = {"red": 0, "yellow": 0, "blue": 0}
        self.pikmin_location_ids = {}  # Maps location names to their AP IDs
        self.last_red_count = 0
        self.last_yellow_count = 0
        self.last_blue_count = 0

    def make_gui(self) -> "type[kvui.GameManager]":
        return P1UI

    async def server_auth(self, password_requested: bool = False) -> None:
        if not self.auth:
            await self.get_username()

        await super().server_auth(password_requested)

        await self.send_connect()


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
        
        locations_to_check = []
        
        # Check Red Pikmin locations
        if red_count > ctx.last_red_count:
            for threshold in range(ctx.last_red_count + 1, red_count + 1):
                location_name = f"Red Pikmin: {threshold}"
                location_id = PIKMIN_LOCATIONS_MAP.get(location_name)
                if location_id and location_id not in ctx.checked_locations:
                    locations_to_check.append(location_id)
            ctx.last_red_count = red_count
        
        # Check Yellow Pikmin locations
        if yellow_count > ctx.last_yellow_count:
            for threshold in range(ctx.last_yellow_count + 1, yellow_count + 1):
                location_name = f"Yellow Pikmin: {threshold}"
                location_id = PIKMIN_LOCATIONS_MAP.get(location_name)
                if location_id and location_id not in ctx.checked_locations:
                    locations_to_check.append(location_id)
            ctx.last_yellow_count = yellow_count
        
        # Check Blue Pikmin locations
        if blue_count > ctx.last_blue_count:
            for threshold in range(ctx.last_blue_count + 1, blue_count + 1):
                location_name = f"Blue Pikmin: {threshold}"
                location_id = PIKMIN_LOCATIONS_MAP.get(location_name)
                if location_id and location_id not in ctx.checked_locations:
                    locations_to_check.append(location_id)
            ctx.last_blue_count = blue_count
        
        # Check all locations that should be checked
        if locations_to_check:
            ctx.locations_checked.update(locations_to_check)
            await ctx.check_locations(locations_to_check)
            logger.info(f"Checked {len(locations_to_check)} Pikmin locations")
        
        # Update counts for UI/logging
        ctx.pikmin_counts["red"] = red_count
        ctx.pikmin_counts["yellow"] = yellow_count
        ctx.pikmin_counts["blue"] = blue_count
        
    except Exception as e:
        logger.debug(f"Error handling Pikmin locations: {e}")


async def handle_areas(ctx: P1Context, game: Game):
    # Count only real ship parts, not fillers (Carrot Pikpik)
    ship_parts_count = 0
    for item in ctx.items_received:
        # Use lookup_in_data to get item name from ID
        item_name = ctx.slot_data.get("item_names", {}).get(item.item, "") if hasattr(ctx, 'slot_data') and ctx.slot_data else ""
        
        # If not in slot_data, try a simpler approach: just count total - carrot pikpik count
        # Since we know Carrot Pikpik has AP ID 71999
        if item.item != 71999:  # 71999 is Carrot Pikpik
            ship_parts_count += 1
    
    total_required = 0

    if ship_parts_count >= 30:  # Olimar succeeds once all 30 parts have been collected
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
    pikmin_locations_initialized = False

    while not ctx.exit_event.is_set():
        try:
            await asyncio.wait_for(ctx.watcher_event.wait(), 1.0)
        except asyncio.TimeoutError:
            pass

        ctx.watcher_event.clear()
        
        # Initialize Pikmin location IDs from P1Data.py map
        if not pikmin_locations_initialized:
            # Use the complete map from P1Data.py
            ctx.pikmin_location_ids = PIKMIN_LOCATIONS_MAP.copy()
            logger.info(f"✓ Loaded {len(ctx.pikmin_location_ids)} Pikmin location IDs from P1Data")
            pikmin_locations_initialized = True

        try:
            if not dme.is_hooked():
                dme.hook()
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
        except Exception as e:
            logger.error(e)
            logger.info("Trying to reconnect to Dolphin...")
            ctx.dolphin_status_text = "??? - Exception Occured"
            dme.un_hook()
            continue

        await handle_parts(ctx, game_version)
        await handle_pikmin_locations(ctx, game_version)
        await handle_areas(ctx, game_version)


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