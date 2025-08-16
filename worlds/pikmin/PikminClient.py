import asyncio
import time
import traceback
import logging
from typing import TYPE_CHECKING, Any, Optional, Set, Dict

from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus
import dolphin_memory_engine
import Utils

from .ReadWrite import *
from .Locations import LOCATION_TABLE, PikminLocation

if TYPE_CHECKING:
    import kvui

# Adresses mémoire importantes
LOCATION_MAP_ADDRESS = 0x808130B8
DAYS_ADDRESS = 0x803A2937
SLOT_NAME_ADDRESS = 0x803FE8A0
TOTAL_PIKMIN_ADRESS = 0x803D6CF0

# Adresses des Pikmin (PAL)
RED_PIKMIN_ADDRESS = 0x803D6CF7
YELLOW_PIKMIN_ADDRESS = 0x803D6CFB  
BLUE_PIKMIN_ADDRESS = 0x803D6CF3
ONION_PIKMIN_ADDRESS = 0x81242804

# Adresses des ship parts (à adapter selon votre mapping)
SHIP_PARTS_BASE_ADDRESS = 0x803A0000  # Base hypothétique, à ajuster

class PikminCommandProcessor(ClientCommandProcessor):
    """Command processor for Pikmin client commands."""
    
    def __init__(self, ctx: CommonContext):
        super().__init__(ctx)

    def _cmd_dolphin(self) -> None:
        """Display current Dolphin connection status."""
        if isinstance(self.ctx, PikminContext):
            logger.info(f"Dolphin Status: {self.ctx.dolphin_status}")
    
    def _cmd_loc(self) -> None:
        """Display current location information."""
        if isinstance(self.ctx, PikminContext):
            logger.info(f"Location Map: {self.ctx.location_map}")
            logger.info(f"Checked Locations: {len(self.ctx.locations_checked)}")
            logger.info(f"Missing Locations: {len(self.ctx.missing_locations)}")
    
    def _cmd_pikmin(self) -> None:
        """Display current Pikmin counts."""
        if isinstance(self.ctx, PikminContext):
            red_count = read_byte(RED_PIKMIN_ADDRESS)
            yellow_count = read_byte(YELLOW_PIKMIN_ADDRESS)  
            blue_count = read_byte(BLUE_PIKMIN_ADDRESS)
            total_pikmin_count_follow = red_count + yellow_count + blue_count

            total_pikmin_count = read_2byte(TOTAL_PIKMIN_ADRESS)

            logger.info(f"Pikmin | Red : {red_count}, Yellow : {yellow_count}, Blue : {blue_count}")
            logger.info(f"Total : {total_pikmin_count_follow}/100 Follow And Total : {total_pikmin_count}")
    
    def _cmd_day(self) -> None:
        """Set day to 2."""
        if isinstance(self.ctx, PikminContext):
            write_byte(DAYS_ADDRESS, 2)
            logger.info(f"Day set 2")
    
    def _cmd_check(self) -> None:
        """Manually trigger location checking for debugging."""
        if isinstance(self.ctx, PikminContext):
            logger.info("Manually checking locations...")
            asyncio.create_task(self.ctx.check_all_locations())

    def _cmd_test_location(self) -> None:
        """Test sending a specific location to the server."""
        if isinstance(self.ctx, PikminContext):
            # Test avec la location "Pikmin Red - 10"
            location_name = "Pikmin Red - 10"
            if location_name in LOCATION_TABLE:
                location_data = LOCATION_TABLE[location_name]
                if location_data.code is not None:
                    location_id = PikminLocation.get_apid(location_data.code)
                    logger.info(f"Testing location {location_name} with AP ID {location_id}")
                    asyncio.create_task(self.ctx.send_location_check(location_id))
                else:
                    logger.info(f"Location {location_name} has no code")
            else:
                logger.info(f"Location {location_name} not found in LOCATION_TABLE")

class PikminContext(CommonContext):
    """Context for Pikmin client."""

    command_processor = PikminCommandProcessor
    game: str = "Pikmin"
    items_handling = 0b001  # Receive items

    def __init__(self, server_address: Optional[str], password: Optional[str]) -> None:
        super().__init__(server_address, password)
        self.dolphin_sync_task: Optional[asyncio.Task[None]] = None
        self.dolphin_status: str = "Disconnected"
        self.awaiting_rom: bool = False
        self.location_map: str = ""
        
        # Game state tracking
        self.previous_pikmin_counts: Dict[str, int] = {"red": 0, "yellow": 0, "blue": 0}
        self.ship_parts_collected: Set[int] = set()
        self.walls_broken: Set[int] = set()
        self.bosses_defeated: Set[int] = set()
        
        # Location checking caches
        self.last_location_check_time: float = 0
        self.location_check_interval: float = 0.5  # Check every 500ms
        
        # Track sent locations to avoid duplicates
        self.sent_locations: Set[int] = set()

    async def disconnect(self, allow_autoreconnect: bool = False) -> None:
        """Disconnect from server and reset game state."""
        self.auth = None
        self.location_map = ""
        self.ship_parts_collected.clear()
        self.walls_broken.clear()
        self.bosses_defeated.clear()
        self.sent_locations.clear()
        await super().disconnect(allow_autoreconnect)

    async def server_auth(self, password_requested: bool = False) -> None:
        """Authenticate with Archipelago server."""
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        if not self.auth:
            if self.awaiting_rom:
                return
            self.awaiting_rom = True
            logger.info("Awaiting connection to Dolphin to get player information.")
            return
        await self.send_connect()

    def make_gui(self) -> type["kvui.GameManager"]:
        """Initialize GUI for Pikmin client."""
        ui = super().make_gui()
        ui.base_title = "Archipelago Pikmin Client"
        return ui

    async def send_location_check(self, location_id: int) -> None:
        """Send a single location check to the server."""
        if not self.server or not self.slot:
            logger.warning("Cannot send location check: not connected to server")
            return
            
        if location_id in self.sent_locations:
            return  # Already sent
            
        try:
            await self.send_msgs([{
                "cmd": "LocationChecks", 
                "locations": [location_id]
            }])
            self.sent_locations.add(location_id)
            
            # Find location name for logging
            location_name = "Unknown"
            for name, data in LOCATION_TABLE.items():
                if data.code is not None and PikminLocation.get_apid(data.code) == location_id:
                    location_name = name
                    break
            
            logger.info(f"Sent location check: {location_name} (ID: {location_id})")
            
        except Exception as e:
            logger.error(f"Error sending location check for ID {location_id}: {e}")

    async def handle_received_items(self) -> None:
        """Handle items received from other players."""
        if not self.items_received:
            return
            
        try:
            # Process each received item
            for network_item in self.items_received:
                item_name = network_item.item
                item_player = network_item.player
                
                # Handle different item types
                if item_name == "Unlock Red Pikmin":
                    self.unlock_pikmin_type("red")
                elif item_name == "Unlock Yellow Pikmin":
                    self.unlock_pikmin_type("yellow")
                elif item_name == "Unlock Blue Pikmin":
                    self.unlock_pikmin_type("blue")
                elif item_name == "Main Engine":
                    self.give_ship_part("Main Engine")
                elif item_name in ["The Impact Site", "The Forest Of Hope", "The Forest Navel", 
                                  "The Distant Spring", "The Final Trial"]:
                    self.unlock_area(item_name)
                elif item_name == "Nectar":
                    self.give_nectar()
                elif item_name == "Carrot Pikpik":
                    self.give_carrot_pikpik()
                    
                logger.info(f"Received {item_name} from {self.player_names.get(item_player, 'Unknown')}")
                
        except Exception as e:
            logger.error(f"Error handling received items: {e}")

    def unlock_pikmin_type(self, pikmin_type: str) -> None:
        """Unlock a specific Pikmin type in game."""
        try:
            # Set the appropriate bit in the Onion address
            current_onion_state = read_4byte(ONION_PIKMIN_ADDRESS)
            
            if pikmin_type == "red":
                new_state = current_onion_state | 18  # Red Onion bit
            elif pikmin_type == "yellow":
                new_state = current_onion_state | 36  # Yellow Onion bit  
            elif pikmin_type == "blue":
                new_state = current_onion_state | 9   # Blue Onion bit
            else:
                return
                
            write_4byte(ONION_PIKMIN_ADDRESS, new_state)
            logger.info(f"Unlocked {pikmin_type} Pikmin")
            
        except Exception as e:
            logger.error(f"Error unlocking {pikmin_type} Pikmin: {e}")

    def unlock_area(self, area_name: str) -> None:
        """Unlock access to a specific area."""
        try:
            # Cette fonction dépend de comment vous gérez l'ouverture des zones
            # Vous devrez identifier les adresses mémoire appropriées
            area_addresses = {
                "The Impact Site": 0x803A3000,
                "The Forest Of Hope": 0x803A3001,
                "The Forest Navel": 0x803A3002,
                "The Distant Spring": 0x803A3003,
                "The Final Trial": 0x803A3004
            }
            
            if area_name in area_addresses:
                write_byte(area_addresses[area_name], 1)
                logger.info(f"Unlocked area: {area_name}")
                
        except Exception as e:
            logger.error(f"Error unlocking area {area_name}: {e}")

    def give_ship_part(self, part_name: str) -> None:
        """Give a specific ship part to the player."""
        try:
            # Vous devrez mapper les noms des ship parts aux adresses mémoire
            if part_name == "Main Engine":
                # Adresse hypothétique pour le Main Engine
                write_byte(0x803A4000, 1)
                logger.info(f"Gave ship part: {part_name}")
                
        except Exception as e:
            logger.error(f"Error giving ship part {part_name}: {e}")

    def give_nectar(self) -> None:
        """Give nectar to the player (increase Pikmin in field)."""
        try:
            # Exemple: ajouter quelques Pikmin rouges
            current_red = read_byte(RED_PIKMIN_ADDRESS)
            if current_red < 100:  # Cap à 100
                write_byte(RED_PIKMIN_ADDRESS, min(current_red + 5, 100))
                logger.info("Gave nectar - added 5 Red Pikmin")
                
        except Exception as e:
            logger.error(f"Error giving nectar: {e}")

    def give_carrot_pikpik(self) -> None:
        """Give carrot pikpik to the player (filler item)."""
        try:
            # Exemple: augmenter légèrement le nombre de Pikmin
            current_red = read_byte(RED_PIKMIN_ADDRESS)
            if current_red < 100:
                write_byte(RED_PIKMIN_ADDRESS, min(current_red + 1, 100))
                logger.info("Gave Carrot Pikpik - added 1 Red Pikmin")
                
        except Exception as e:
            logger.error(f"Error giving carrot pikpik: {e}")

    def check_pikmin_milestones(self) -> Set[int]:
        """Check Pikmin count milestones and return newly achieved location IDs."""
        new_locations = set()
        
        try:
            current_red = read_byte(RED_PIKMIN_ADDRESS)
            current_yellow = read_byte(YELLOW_PIKMIN_ADDRESS)
            current_blue = read_byte(BLUE_PIKMIN_ADDRESS)
            
            logger.debug(f"Current Pikmin counts - Red: {current_red}, Yellow: {current_yellow}, Blue: {current_blue}")
            logger.debug(f"Previous Pikmin counts - Red: {self.previous_pikmin_counts['red']}, Yellow: {self.previous_pikmin_counts['yellow']}, Blue: {self.previous_pikmin_counts['blue']}")
            
            # Check red Pikmin milestones
            for milestone in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
                if (current_red >= milestone and 
                    self.previous_pikmin_counts["red"] < milestone):
                    # Find the location ID for this milestone
                    location_name = f"Pikmin Red - {milestone}"
                    logger.debug(f"Checking location: {location_name}")
                    if location_name in LOCATION_TABLE:
                        location_data = LOCATION_TABLE[location_name]
                        if location_data.code is not None:
                            ap_id = PikminLocation.get_apid(location_data.code)
                            new_locations.add(ap_id)
                            logger.info(f"Achieved milestone: {location_name} (AP ID: {ap_id})")
                    else:
                        logger.warning(f"Location {location_name} not found in LOCATION_TABLE")
            
            # Update previous counts
            self.previous_pikmin_counts["red"] = current_red
            self.previous_pikmin_counts["yellow"] = current_yellow
            self.previous_pikmin_counts["blue"] = current_blue
            
        except Exception as e:
            logger.error(f"Error checking Pikmin milestones: {e}")
            
        return new_locations

    def check_ship_parts(self) -> Set[int]:
        """Check for newly collected ship parts."""
        new_locations = set()
        
        try:
            # Hypothetical ship parts checking - vous devrez adapter selon vos adresses réelles
            for i in range(30):  # Supposons 30 ship parts maximum
                ship_part_address = SHIP_PARTS_BASE_ADDRESS + i
                if read_byte(ship_part_address) == 1 and i not in self.ship_parts_collected:
                    self.ship_parts_collected.add(i)
                    # Trouver la location correspondante
                    # Cette logique dépend de comment vous mappez les ship parts aux locations
                    location_id = PikminLocation.get_apid(100 + i)  # Offset pour les ship parts
                    new_locations.add(location_id)
                    
        except Exception as e:
            logger.error(f"Error checking ship parts: {e}")
            
        return new_locations

    def check_walls_and_bridges(self) -> Set[int]:
        """Check for newly broken walls and built bridges."""
        new_locations = set()
        
        try:
            # Exemple de vérification des murs - à adapter selon vos adresses
            # Vous devrez identifier les adresses mémoire pour chaque mur/pont
            wall_addresses = {
                200: 0x803A1000,  # Forest of Hope - Red Wall 1
                201: 0x803A1001,  # Forest of Hope - Red Wall 2
                # Ajoutez d'autres adresses...
            }
            
            for location_code, address in wall_addresses.items():
                if read_byte(address) == 1 and location_code not in self.walls_broken:
                    self.walls_broken.add(location_code)
                    location_id = PikminLocation.get_apid(location_code)
                    new_locations.add(location_id)
                    
        except Exception as e:
            logger.error(f"Error checking walls and bridges: {e}")
            
        return new_locations

    def check_bosses(self) -> Set[int]:
        """Check for newly defeated bosses."""
        new_locations = set()
        
        try:
            # Exemple de vérification des boss - à adapter
            boss_addresses = {
                400: 0x803A2000,  # Armored Cannon Beetle
                401: 0x803A2001,  # Burrowing Snagret
                402: 0x803A2002,  # Smoky Progg
                403: 0x803A2003,  # Emperor Bulblax
            }
            
            for location_code, address in boss_addresses.items():
                if read_byte(address) == 1 and location_code not in self.bosses_defeated:
                    self.bosses_defeated.add(location_code)
                    location_id = PikminLocation.get_apid(location_code)
                    new_locations.add(location_id)
                    
        except Exception as e:
            logger.error(f"Error checking bosses: {e}")
            
        return new_locations

    async def check_all_locations(self) -> None:
        """Check all location types for changes."""
        current_time = time.time()
        
        # Rate limit location checking
        if current_time - self.last_location_check_time < self.location_check_interval:
            return
            
        self.last_location_check_time = current_time
        
        try:
            new_location_ids = set()
            
            # Check different types of locations
            new_location_ids.update(self.check_pikmin_milestones())
            new_location_ids.update(self.check_ship_parts())
            new_location_ids.update(self.check_walls_and_bridges())
            new_location_ids.update(self.check_bosses())
            
            # Send newly found locations to server one by one
            for location_id in new_location_ids:
                if location_id not in self.sent_locations:
                    await self.send_location_check(location_id)
                    
        except Exception as e:
            logger.error(f"Error in check_all_locations: {e}")

def check_ingame() -> bool:
    """Check if player is currently in-game."""
    try:
        location_map = read_string(LOCATION_MAP_ADDRESS, 35)
        return location_map not in ["", "sea_T", "Name"]
    except:
        return False

async def dolphin_sync_task(ctx: PikminContext) -> None:
    """Main sync task for Dolphin connection and game state monitoring."""
    logger.info("Starting Dolphin connector. Use /dolphin for status information.")
    sleep_time = 0.0
    
    while not ctx.exit_event.is_set():
        if sleep_time > 0.0:
            try:
                await asyncio.wait_for(ctx.watcher_event.wait(), sleep_time)
            except asyncio.TimeoutError:
                pass
            sleep_time = 0.0
        ctx.watcher_event.clear()

        try:
            if dolphin_memory_engine.is_hooked() and ctx.dolphin_status == "Connected":
                # Update location map
                ctx.location_map = read_string(LOCATION_MAP_ADDRESS, 0x40)
                
                # Check if we're in game and authenticated
                if ctx.slot is not None and check_ingame():
                    # Monitor game state and check for new locations
                    await ctx.check_all_locations()
                    
                    # Handle received items
                    await ctx.handle_received_items()
                    
                elif not ctx.auth:
                    # Try to get authentication from game
                    try:
                        ctx.auth = read_string(SLOT_NAME_ADDRESS, 0x40).strip()
                        if ctx.auth and ctx.awaiting_rom:
                            await ctx.server_auth()
                    except:
                        pass
                
                sleep_time = 0.1
                
            else:
                # Handle Dolphin connection
                if ctx.dolphin_status == "Connected":
                    logger.info("Connection to Dolphin lost, reconnecting...")
                    ctx.dolphin_status = "Disconnected"
                    
                logger.info("Attempting to connect to Dolphin...")
                dolphin_memory_engine.hook()
                
                if dolphin_memory_engine.is_hooked():
                    # Verify we have the correct game (PAL Pikmin)
                    game_id = dolphin_memory_engine.read_bytes(0x80000000, 6)
                    if game_id != b"GPIP01":  # PAL version ID
                        logger.info("Wrong game detected. Please load Pikmin PAL version.")
                        ctx.dolphin_status = "Wrong Game"
                        dolphin_memory_engine.un_hook()
                        sleep_time = 5
                    else:
                        logger.info("Successfully connected to Dolphin with Pikmin PAL.")
                        ctx.dolphin_status = "Connected"
                        ctx.locations_checked = set()
                        ctx.sent_locations.clear()
                        
                        # Reset game state tracking
                        ctx.ship_parts_collected.clear()
                        ctx.walls_broken.clear()
                        ctx.bosses_defeated.clear()
                        
                        # Reset previous counts to current values to avoid false positives
                        try:
                            ctx.previous_pikmin_counts["red"] = read_byte(RED_PIKMIN_ADDRESS)
                            ctx.previous_pikmin_counts["yellow"] = read_byte(YELLOW_PIKMIN_ADDRESS)
                            ctx.previous_pikmin_counts["blue"] = read_byte(BLUE_PIKMIN_ADDRESS)
                        except:
                            pass
                else:
                    logger.info("Failed to connect to Dolphin. Retrying in 5 seconds...")
                    ctx.dolphin_status = "Disconnected"
                    await ctx.disconnect()
                    sleep_time = 5
                    continue
                    
        except Exception as e:
            dolphin_memory_engine.un_hook()
            logger.error(f"Error in dolphin_sync_task: {traceback.format_exc()}")
            ctx.dolphin_status = "Error"
            await ctx.disconnect()
            sleep_time = 5
            continue

def main(connect: Optional[str] = None, password: Optional[str] = None) -> None:
    """Run the main async loop for Pikmin client."""
    Utils.init_logging("Pikmin Client", exception_logger="Client")

    async def _main(connect: Optional[str], password: Optional[str]) -> None:
        ctx = PikminContext(connect, password)
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="ServerLoop")
        
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        
        await asyncio.sleep(1)
        ctx.dolphin_sync_task = asyncio.create_task(dolphin_sync_task(ctx), name="DolphinSync")

        await ctx.exit_event.wait()
        ctx.watcher_event.set()
        ctx.server_address = None

        await ctx.shutdown()
        if ctx.dolphin_sync_task:
            await ctx.dolphin_sync_task
    
    import colorama
    colorama.init()
    asyncio.run(_main(connect, password))
    colorama.deinit()

if __name__ == "__main__":
    parser = get_base_parser()
    args = parser.parse_args()
    main(args.connect, args.password)