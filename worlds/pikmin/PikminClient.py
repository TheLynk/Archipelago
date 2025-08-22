import asyncio
import time
import traceback
import logging
import re
from typing import TYPE_CHECKING, Any, Optional, Set, Dict

from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus, NetworkItem
import dolphin_memory_engine
import Utils

from .ReadWrite import *
from .Locations import LOCATION_TABLE, PikminLocation

if TYPE_CHECKING:
    import kvui

# Adresses mémoire importantes
LOCATION_MAP_ADDRESS = 0x808130B0
DAYS_ADDRESS = 0x803A2937
TOTAL_PIKMIN_ADRESS = 0x803D6CF0

# Adresses des Pikmin (PAL)
RED_PIKMIN_ADDRESS = 0x803D6CF7
YELLOW_PIKMIN_ADDRESS = 0x803D6CFB  
BLUE_PIKMIN_ADDRESS = 0x803D6CF3
ONION_PIKMIN_ADDRESS = 0x81242804

# Custom Adresse pour écriture et lecture
SLOT_NAME_ADDRESS = 0x7E000000
DEBUG_MODE_ADDRESS = 0x7E000010

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

    def _cmd_debug(self) -> None:
        """check status debug mode"""
        debug_mode = read_string(DEBUG_MODE_ADDRESS, 16)
        logger.info(f"{debug_mode}")

    def _cmd_toggle_debug(self) -> None:
        """Switch "no debug" to "debug" And "debug" to "no debug" """
        debug_mode = read_string(DEBUG_MODE_ADDRESS, 16)
        if debug_mode != "false":
            if debug_mode != "true":
                write_string(DEBUG_MODE_ADDRESS, "false")
                debug_mode = read_string(DEBUG_MODE_ADDRESS, 16)
                logger.info(f"Debug Mode is not set but is set to FALSE")

        if debug_mode == "false":
            write_string(DEBUG_MODE_ADDRESS, "true")
            logger.info(f"Debug Mode is TRUE now")
            
        else:
            write_string(DEBUG_MODE_ADDRESS, "false")
            logger.info(f"Debug Mode is FALSE now")
        
        debug_mode = read_string(DEBUG_MODE_ADDRESS, 16)

    def _cmd_test_unlock(self) -> None:
        """Test unlocking different Pikmin types."""
        if isinstance(self.ctx, PikminContext):
            import sys
            
            # Get the color argument
            args = sys.argv if hasattr(sys, 'argv') else []
            color = "red"  # default
            
            # Simple argument parsing for testing
            try:
                # Look for color in command line or default to red
                if len(args) > 1 and args[-1] in ["red", "yellow", "blue"]:
                    color = args[-1]
            except:
                pass
                
            logger.info(f"Testing {color} Pikmin unlock...")
            
            # Show current onion state
            current_state = read_byte(ONION_PIKMIN_ADDRESS)
            logger.info(f"Current onion state: {current_state:08X}")
            
            # Test unlock
            success = self.ctx.unlock_pikmin_type(color)
            
            # Show new state
            new_state = read_byte(ONION_PIKMIN_ADDRESS)
            logger.info(f"New onion state: {new_state:08X}")
            logger.info(f"Unlock {'successful' if success else 'failed'}")

    def _cmd_onion_state(self) -> None:
        """Display current onion state for debugging."""
        try:
            current_state = read_byte(ONION_PIKMIN_ADDRESS)
            logger.info(f"Onion state: {current_state:08X} ({current_state})")
            logger.info(f"Target state: {self.ctx.target_onion_state:08X} ({self.ctx.target_onion_state})")
            logger.info(f"Control active: {self.ctx.onion_control_active}")
            
            # Decode the bits
            red_unlocked = bool(current_state & 0x12)
            yellow_unlocked = bool(current_state & 0x24)
            blue_unlocked = bool(current_state & 0x09)
            
            logger.info(f"Current state - Red: {'✓' if red_unlocked else '✗'}, Yellow: {'✓' if yellow_unlocked else '✗'}, Blue: {'✓' if blue_unlocked else '✗'}")
            logger.info(f"Tracked unlocks: {', '.join(sorted(self.ctx.unlocked_pikmin_types)) if self.ctx.unlocked_pikmin_types else 'None'}")
            
        except Exception as e:
            logger.error(f"Error reading onion state: {e}")

    def _cmd_reset_onions(self) -> None:
        """Reset onion control and clear all unlocked types."""
        if isinstance(self.ctx, PikminContext):
            self.ctx.unlocked_pikmin_types.clear()
            self.ctx.target_onion_state = 0
            self.ctx.onion_control_active = False
            
            # Write 0 to onion address to clear everything
            write_byte(ONION_PIKMIN_ADDRESS, 0)
            
            logger.info("🔓 Onion control reset - all types locked")
            
    def _cmd_force_onion_write(self) -> None:
        """Force an immediate onion state write."""
        if isinstance(self.ctx, PikminContext):
            try:
                target = self.ctx.calculate_target_onion_state()
                write_byte(ONION_PIKMIN_ADDRESS, target)
                
                current = read_byte(ONION_PIKMIN_ADDRESS)
                logger.info(f"Forced onion write - Target: {target:08X}, Result: {current:08X}")
                
            except Exception as e:
                logger.error(f"Error forcing onion write: {e}")


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
        
        # Track send locations to avoid duplicates
        self.sent_locations: Set[int] = set()
        
        # Pikmin unlock state management
        self.unlocked_pikmin_types: Set[str] = set()  # Track which types we've unlocked
        self.onion_control_active: bool = False  # Whether we're controlling onion state
        self.last_onion_write_time: float = 0
        self.onion_write_interval: float = 1.0  # Write every 1 second
        self.target_onion_state: int = 0  # The state we want to maintain

    async def disconnect(self, allow_autoreconnect: bool = False) -> None:
        """Disconnect from server and reset game state."""
        self.auth = None
        self.location_map = ""
        self.ship_parts_collected.clear()
        self.walls_broken.clear()
        self.bosses_defeated.clear()
        self.sent_locations.clear()
        
        # Reset Pikmin unlock state
        self.unlocked_pikmin_types.clear()
        self.onion_control_active = False
        self.target_onion_state = 0
        
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

    def on_package(self, cmd: str, args: dict) -> None:
        """Handle incoming network packages including DataPackage."""
        if cmd == "Connected":
            # Store slot data and handle connection
            if "slot_data" in args:
                self.slot_data = args["slot_data"]
            
            # Request DataPackage for our game if not already cached
            asyncio.create_task(self.send_msgs([{
                "cmd": "GetDataPackage", 
                "games": [self.game]
            }]))
            
        elif cmd == "DataPackage":
            # Handle DataPackage response
            if "data" in args and "games" in args["data"]:
                game_data = args["data"]["games"]
                if self.game in game_data:
                    # Cache the datapackage data
                    self.stored_data.update(game_data[self.game])
                    logger.info(f"DataPackage loaded for {self.game}")
        
        # Call parent handler for other commands
        super().on_package(cmd, args)

    def make_gui(self) -> type["kvui.GameManager"]:
        """Initialize GUI for Pikmin client."""
        ui = super().make_gui()
        ui.base_title = "Archipelago Pikmin Client"
        return ui

    async def send_location_check(self, location_id: int) -> None:
        """Send a single location check to the server."""

        debug_mode = read_string(DEBUG_MODE_ADDRESS, 16)
        
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
            
            if debug_mode == "true":
                logger.info(f"Send location check: {location_name} (ID: {location_id})")
            
        except Exception as e:
            logger.error(f"Error sending location check for ID {location_id}: {e}")

    async def handle_received_items(self) -> None:
        """Handle items received from other players."""
        if not self.items_received:
            return
            
        try:
            debug_mode = read_string(DEBUG_MODE_ADDRESS, 16)
            
            # Track items we've already processed to avoid duplicates
            if not hasattr(self, 'processed_items_count'):
                self.processed_items_count = 0
            
            # Only process new items
            new_items = self.items_received[self.processed_items_count:]
            
            for network_item in new_items:
                item_name = network_item.item
                item_player = network_item.player
                player_name = self.player_names.get(item_player, f"Player {item_player}")
                
                # Handle different item types
                success = False
                if item_name == "Unlock Red Pikmin":
                    success = self.unlock_pikmin_type("red")
                elif item_name == "Unlock Yellow Pikmin":
                    success = self.unlock_pikmin_type("yellow")
                elif item_name == "Unlock Blue Pikmin":
                    success = self.unlock_pikmin_type("blue")
                elif "Pikmin" in item_name and any(color in item_name for color in ["Red", "Yellow", "Blue"]):
                    # Handle Pikmin count items (if you have them)
                    success = self.give_pikmin_from_item(item_name)
                else:
                    # Handle other items (ship parts, upgrades, etc.)
                    success = self.handle_other_items(item_name)
                
                if success:
                    logger.info(f"Applied {item_name} from {player_name}")
                    if debug_mode == "true":
                        logger.debug(f"Item {item_name} successfully processed")
                else:
                    logger.warning(f"Failed to apply {item_name} from {player_name}")
                
            # Update processed items count
            self.processed_items_count = len(self.items_received)
                
        except Exception as e:
            logger.error(f"Error handling received items: {e}")
            if debug_mode == "true":
                logger.error(f"Full traceback: {traceback.format_exc()}")

    def calculate_target_onion_state(self) -> int:
        """Calculate the target onion state based on unlocked Pikmin types."""
        state = 0
        
        if "red" in self.unlocked_pikmin_types:
            state |= 0x12  # Red onion bits
        if "yellow" in self.unlocked_pikmin_types:
            state |= 0x24  # Yellow onion bits  
        if "blue" in self.unlocked_pikmin_types:
            state |= 0x09  # Blue onion bits
            
        return state

    async def maintain_onion_state(self) -> None:
        """Maintain control over the onion state to prevent game interference."""
        current_time = time.time()
        
        # Only write every second to avoid spam
        if current_time - self.last_onion_write_time < self.onion_write_interval:
            return
            
        self.last_onion_write_time = current_time
        
        try:
            debug_mode = read_string(DEBUG_MODE_ADDRESS, 16)
            
            # Calculate what the onion state should be
            target_state = self.calculate_target_onion_state()
            
            # Read current state
            current_state = read_byte(ONION_PIKMIN_ADDRESS)
            
            # Always enforce our target state
            if current_state != target_state:
                write_byte(ONION_PIKMIN_ADDRESS, target_state)
                
                if debug_mode == "true":
                    logger.debug(f"Onion state corrected: {current_state:08X} → {target_state:08X}")
                    logger.debug(f"Unlocked types: {', '.join(self.unlocked_pikmin_types) if self.unlocked_pikmin_types else 'None'}")
            
            self.target_onion_state = target_state
            
        except Exception as e:
            logger.error(f"Error maintaining onion state: {e}")

    def start_onion_control(self) -> None:
        """Start controlling the onion state."""
        if not self.onion_control_active:
            self.onion_control_active = True
            logger.info("Onion state control activated")

    def unlock_pikmin_type(self, pikmin_type: str) -> bool:
        """Unlock a specific Pikmin type in game."""
        try:
            debug_mode = read_string(DEBUG_MODE_ADDRESS, 16)
            
            # Start onion control if not already active
            self.start_onion_control()
            
            # Check if already unlocked
            if pikmin_type in self.unlocked_pikmin_types:
                if debug_mode == "true":
                    logger.debug(f"{pikmin_type.title()} Pikmin already unlocked")
                return True
            
            # Add to unlocked types
            self.unlocked_pikmin_types.add(pikmin_type)
            
            # Calculate and apply new onion state
            new_target_state = self.calculate_target_onion_state()
            write_byte(ONION_PIKMIN_ADDRESS, new_target_state)
            
            # Verify the write was successful
            verified_state = read_byte(ONION_PIKMIN_ADDRESS)
            
            if debug_mode == "true":
                logger.debug(f"Onion state updated: {self.target_onion_state:08X} → {new_target_state:08X}")
                logger.debug(f"Verified state: {verified_state:08X}")
            
            self.target_onion_state = new_target_state
            
            if verified_state == new_target_state:
                logger.info(f"Successfully unlocked {pikmin_type.title()} Pikmin!")
                logger.info(f"Currently unlocked: {', '.join(sorted(self.unlocked_pikmin_types))}")
                
                # Optional: Give some starting Pikmin of this type
                self.give_starting_pikmin(pikmin_type)
                return True
            else:
                logger.error(f"Failed to verify {pikmin_type} Pikmin unlock")
                # Remove from unlocked types if verification failed
                self.unlocked_pikmin_types.discard(pikmin_type)
                return False
                
        except Exception as e:
            logger.error(f"Error unlocking {pikmin_type} Pikmin: {e}")
            # Remove from unlocked types if error occurred
            self.unlocked_pikmin_types.discard(pikmin_type)
            return False

    def give_starting_pikmin(self, pikmin_type: str) -> None:
        """Give some starting Pikmin when a type is first unlocked."""
        try:
            debug_mode = read_string(DEBUG_MODE_ADDRESS, 16)
            starting_count = 5  # Give 5 Pikmin to start
            
            if pikmin_type == "red":
                current_count = read_byte(RED_PIKMIN_ADDRESS)
                if current_count < starting_count:
                    write_byte(RED_PIKMIN_ADDRESS, starting_count)
                    if debug_mode == "true":
                        logger.debug(f"Gave {starting_count} red Pikmin (was {current_count})")
                        
            elif pikmin_type == "yellow":
                current_count = read_byte(YELLOW_PIKMIN_ADDRESS)
                if current_count < starting_count:
                    write_byte(YELLOW_PIKMIN_ADDRESS, starting_count)
                    if debug_mode == "true":
                        logger.debug(f"Gave {starting_count} yellow Pikmin (was {current_count})")
                        
            elif pikmin_type == "blue":
                current_count = read_byte(BLUE_PIKMIN_ADDRESS)
                if current_count < starting_count:
                    write_byte(BLUE_PIKMIN_ADDRESS, starting_count)
                    if debug_mode == "true":
                        logger.debug(f"Gave {starting_count} blue Pikmin (was {current_count})")
                        
        except Exception as e:
            logger.error(f"Error giving starting {pikmin_type} Pikmin: {e}")

    def check_pikmin_milestones(self) -> Set[int]:
        """Check Pikmin count milestones and return newly achieved location IDs."""
        new_locations = set()
        debug_mode = read_string(DEBUG_MODE_ADDRESS, 16)
        
        try:
            current_red = read_byte(RED_PIKMIN_ADDRESS)
            current_yellow = read_byte(YELLOW_PIKMIN_ADDRESS)
            current_blue = read_byte(BLUE_PIKMIN_ADDRESS)
            
            if debug_mode == "true":
                logger.debug(f"Current Pikmin counts - Red: {current_red}, Yellow: {current_yellow}, Blue: {current_blue}")
                logger.debug(f"Previous Pikmin counts - Red: {self.previous_pikmin_counts['red']}, Yellow: {self.previous_pikmin_counts['yellow']}, Blue: {self.previous_pikmin_counts['blue']}")
            
            # Check red Pikmin milestones
            for milestone in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
                if (current_red >= milestone and 
                    self.previous_pikmin_counts["red"] < milestone):
                    # Find the location ID for this milestone
                    location_name = f"Pikmin Red - {milestone}"
                    if debug_mode == "true":
                        logger.debug(f"Checking location: {location_name}")

                    if location_name in LOCATION_TABLE:
                        location_data = LOCATION_TABLE[location_name]
                        if location_data.code is not None:
                            ap_id = PikminLocation.get_apid(location_data.code)
                            new_locations.add(ap_id)
                            if debug_mode == "true":
                                logger.info(f"Achieved milestone: {location_name} (AP ID: {ap_id})")
                    else:
                        logger.warning(f"Location {location_name} not found in LOCATION_TABLE")

            # Check Yellow Pikmin milestones
            for milestone in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
                if (current_yellow >= milestone and 
                    self.previous_pikmin_counts["yellow"] < milestone):
                    # Find the location ID for this milestone
                    location_name = f"Pikmin Yellow - {milestone}"
                    if debug_mode == "true":
                        logger.debug(f"Checking location: {location_name}")

                    if location_name in LOCATION_TABLE:
                        location_data = LOCATION_TABLE[location_name]
                        if location_data.code is not None:
                            ap_id = PikminLocation.get_apid(location_data.code)
                            new_locations.add(ap_id)
                            if debug_mode == "true":
                                logger.info(f"Achieved milestone: {location_name} (AP ID: {ap_id})")
                    else:
                        logger.warning(f"Location {location_name} not found in LOCATION_TABLE")

            # Check Blue Pikmin milestones
            for milestone in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
                if (current_blue >= milestone and 
                    self.previous_pikmin_counts["blue"] < milestone):
                    # Find the location ID for this milestone
                    location_name = f"Pikmin Blue - {milestone}"
                    if debug_mode == "true":
                        logger.debug(f"Checking location: {location_name}")

                    if location_name in LOCATION_TABLE:
                        location_data = LOCATION_TABLE[location_name]
                        if location_data.code is not None:
                            ap_id = PikminLocation.get_apid(location_data.code)
                            new_locations.add(ap_id)
                            if debug_mode == "true":
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
            for i in range(30): 
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
            
            # Send newly found locations to server one by one
            for location_id in new_location_ids:
                if location_id not in self.sent_locations:
                    await self.send_location_check(location_id)
                    
        except Exception as e:
            logger.error(f"Error in check_all_locations: {e}")

    async def manage_game_state(self) -> None:
        """Manage overall game state including onion control."""
        try:
            # Always maintain onion state control when connected and authenticated
            if self.onion_control_active:
                await self.maintain_onion_state()
                
            # Check for location updates
            await self.check_all_locations()
            
            # Handle received items
            await self.handle_received_items()
            
        except Exception as e:
            logger.error(f"Error in manage_game_state: {e}")

def check_ingame() -> bool:
    """Check if player is currently in-game."""
    try:
        location_map = read_string(LOCATION_MAP_ADDRESS, 37)
        return location_map in ["courses/courses/practice/practice.mod", "courses/courses/stage1/forest.mod", "courses/stage2/cave.mod", "courses/courses/stage3/yakusima.mod", "courses/laststage/garden.mod"]
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
                    # Use the new unified game state management
                    await ctx.manage_game_state()
                    
                elif not ctx.auth:
                    # Try to get authentication from game
                    try:
                        ctx.auth = read_string(SLOT_NAME_ADDRESS, 0x40).strip()
                        if ctx.auth == read_string(SLOT_NAME_ADDRESS, 0x40).strip() is not set:
                            ctx.auth = "Player1"
                            write_string(SLOT_NAME_ADDRESS, "Player1")
                            
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
                        
                        # Reset Pikmin unlock tracking
                        ctx.unlocked_pikmin_types.clear()
                        ctx.onion_control_active = False
                        ctx.target_onion_state = 0
                        
                        # Start onion control immediately
                        ctx.start_onion_control()
                        
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