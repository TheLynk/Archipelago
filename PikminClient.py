import asyncio
import dolphin_memory_engine
from CommonClient import CommonContext, server_loop, get_base_parser, logger
import Utils

GAME_NAME = "Pikmin"
PIKMIN_GAME_ID = b"GPIP01"
SHIP_PART_COUNT = 30
SHIP_PART_COLLECTED_FLAG_START_ADDRESS = 0x8042321C
LOCATION_ID_BASE = 5000000

class PikminContext(CommonContext):
    game = GAME_NAME
    items_handling = 0b111

    def __init__(self, server_address, password):
        super().__init__(server_address, password)
        self.last_checked_flags = bytes([0] * SHIP_PART_COUNT)

    def on_package(self, cmd: str, args: dict):
        if cmd == 'Connected':
            logger.info("Connected to the server. Ready to play Pikmin!")
        elif cmd == 'ReceivedItems':
            for item in args['items']:
                item_name = self.item_names.get(item.item, f"Unknown item ({item.item})")
                player_name = self.player_names.get(item.player, f"Unknown player ({item.player})")
                logger.info(f"Received {item_name} from {player_name}.")

async def pikmin_monitor(ctx: PikminContext):
    """Main asyncio task to monitor the game state."""
    while True:
        try:
            logger.info("Attempting to hook to Dolphin...")
            dolphin_memory_engine.hook()
            game_id = dolphin_memory_engine.read_bytes(0x80000000, 6)
            if game_id == PIKMIN_GAME_ID:
                logger.info("Pikmin found! Monitoring for ship parts.")
                break
            else:
                logger.warning(f"Found game {game_id.decode(errors='ignore')}, but waiting for Pikmin (GPIP01).")
                dolphin_memory_engine.un_hook()
        except RuntimeError:
            logger.info("Dolphin not found or game not running. Retrying in 5 seconds...")
        await asyncio.sleep(5)

    while True:
        try:
            if not dolphin_memory_engine.is_hooked():
                logger.warning("Dolphin disconnected. Attempting to re-hook...")
                await pikmin_monitor(ctx)
                return

            current_flags = dolphin_memory_engine.read_bytes(SHIP_PART_COLLECTED_FLAG_START_ADDRESS, SHIP_PART_COUNT)
            if current_flags != ctx.last_checked_flags:
                newly_collected = []
                for i in range(SHIP_PART_COUNT):
                    if (current_flags[i] & 1) and not (ctx.last_checked_flags[i] & 1):
                        location_id = LOCATION_ID_BASE + i
                        newly_collected.append(location_id)
                if newly_collected:
                    logger.info(f"Sending newly collected part locations: {newly_collected}")
                    await ctx.send_msgs([{"cmd": "LocationChecks", "locations": newly_collected}])
                ctx.last_checked_flags = current_flags
        except Exception as e:
            logger.error(f"Error reading memory: {e}")
        await asyncio.sleep(0.5)

async def main(args):
    """Main entry point."""
    ctx = PikminContext(args.connect, args.password)
    ctx.server_address = args.connect
    
    server_task = asyncio.create_task(server_loop(ctx))
    monitor_task = asyncio.create_task(pikmin_monitor(ctx))
    
    await asyncio.gather(server_task, monitor_task)

if __name__ == '__main__':
    Utils.init_logging("PikminClient", exception_logger="Client")
    parser = get_base_parser(description="Pikmin Client for Archipelago.")
    args = parser.parse_args()
    asyncio.run(main(args))