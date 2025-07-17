import asyncio
import logging
import typing
from typing import Dict, Set

import dolphin_memory_engine

from NetUtils import ClientStatus
from CommonClient import CommonContext, server_loop, gui_enabled, ClientCommandProcessor, logger, get_base_parser
from .Items import item_table
from .Locations import location_table


class Pikmin1CommandProcessor(ClientCommandProcessor):
    def _cmd_pikmin(self):
        """Show current Pikmin count."""
        if isinstance(self.ctx, Pikmin1Context):
            red_count = self.ctx.red_pikmin_count
            self.output(f"Current Red Pikmin following: {red_count}")


class Pikmin1Context(CommonContext):
    command_processor = Pikmin1CommandProcessor
    game = "Pikmin 1"
    items_handling = 0b001  # We handle our own items
    
    def __init__(self, server_address, password):
        super().__init__(server_address, password)
        self.red_pikmin_count = 0
        self.last_red_pikmin_count = 0
        self.checked_locations: Set[str] = set()
        self.dolphin_connected = False
        
    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()
        
    def on_package(self, cmd: str, args: dict):
        if cmd == "Connected":
            self.game = self.slot_info[self.slot].game
            
    def run_gui(self):
        """Launch the GUI."""
        from kvui import GameManager
        
        class Pikmin1Manager(GameManager):
            logging_pairs = [
                ("Client", "Archipelago")
            ]
            base_title = "Archipelago Pikmin 1 Client"
            
        self.ui = Pikmin1Manager(self)
        self.ui_task = asyncio.create_task(self.ui.async_run(), name="UI")
        
    async def read_dolphin_memory(self):
        """Read memory from Dolphin emulator."""
        try:
            if not self.dolphin_connected:
                # Try to connect to Dolphin
                if dolphin_memory_engine.is_hooked():
                    self.dolphin_connected = True
                    logger.info("Connected to Dolphin emulator")
                else:
                    dolphin_memory_engine.hook()
                    if dolphin_memory_engine.is_hooked():
                        self.dolphin_connected = True
                        logger.info("Successfully hooked to Dolphin emulator")
                    else:
                        return
            
            # Read red Pikmin count from memory
            try:
                self.red_pikmin_count = dolphin_memory_engine.read_byte(0x803D6CF7)
                
                # Check if count changed
                if self.red_pikmin_count != self.last_red_pikmin_count:
                    logger.info(f"Red Pikmin count changed: {self.last_red_pikmin_count} -> {self.red_pikmin_count}")
                    self.last_red_pikmin_count = self.red_pikmin_count
                    
                    # Check location milestones
                    await self.check_pikmin_milestones()
                    
            except Exception as e:
                logger.error(f"Error reading memory: {e}")
                self.dolphin_connected = False
                
        except Exception as e:
            logger.error(f"Error connecting to Dolphin: {e}")
            self.dolphin_connected = False
            
    async def check_pikmin_milestones(self):
        """Check if any Pikmin milestones have been reached."""
        locations_to_check = []
        
        # Check red Pikmin milestones
        if self.red_pikmin_count >= 10 and "Pikmin Rouge 10" not in self.checked_locations:
            locations_to_check.append("Pikmin Rouge 10")
            self.checked_locations.add("Pikmin Rouge 10")
            
        if self.red_pikmin_count >= 20 and "Pikmin Rouge 20" not in self.checked_locations:
            locations_to_check.append("Pikmin Rouge 20")
            self.checked_locations.add("Pikmin Rouge 20")
            
        # Send location checks to server
        if locations_to_check:
            location_ids = [location_table[loc_name].code for loc_name in locations_to_check]
            await self.send_msgs([{
                "cmd": "LocationChecks",
                "locations": location_ids
            }])
            logger.info(f"Checked locations: {locations_to_check}")
            
    async def game_watcher(self, ctx):
        """Main game watching loop."""
        while not ctx.exit_event.is_set():
            try:
                await self.read_dolphin_memory()
                await asyncio.sleep(1)  # Check every second
            except Exception as e:
                logger.error(f"Error in game watcher: {e}")
                await asyncio.sleep(5)  # Wait longer on error


def launch():
    """Launch the Pikmin 1 client."""
    async def main(args):
        ctx = Pikmin1Context(args.connect, args.password)
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
        
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        
        # Start game watcher
        ctx.watcher_task = asyncio.create_task(ctx.game_watcher(ctx), name="game watcher")
        
        await ctx.exit_event.wait()
        ctx.server_task.cancel()
        ctx.watcher_task.cancel()
        
    import colorama
    
    parser = get_base_parser(description="Pikmin 1 Client, for text interfacing.")
    args, rest = parser.parse_known_args()
    
    colorama.init()
    asyncio.run(main(args))
    colorama.deinit()


if __name__ == "__main__":
    launch()