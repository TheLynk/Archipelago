import asyncio
import struct
from typing import Dict, Any, Optional, Set
from CommonClient import CommonContext, server_loop, gui_enabled, ClientCommandProcessor
from NetUtils import ClientStatus
import logging

logger = logging.getLogger(__name__)

class PikminCommandProcessor(ClientCommandProcessor):
    """Command processor for Pikmin client"""
    
    def _cmd_connect_dolphin(self):
        """Connect to Dolphin emulator"""
        if isinstance(self.ctx, PikminContext):
            asyncio.create_task(self.ctx.connect_to_dolphin())
    
    def _cmd_check_pikmin(self):
        """Check current Pikmin count"""
        if isinstance(self.ctx, PikminContext):
            asyncio.create_task(self.ctx.check_pikmin_count())

class PikminContext(CommonContext):
    """Context for Pikmin client"""
    
    command_processor = PikminCommandProcessor
    game = "Pikmin"
    items_handling = 0b111  # Full item handling
    
    def __init__(self, server_address: Optional[str], password: Optional[str]):
        super().__init__(server_address, password)
        
        # Game state
        self.red_pikmin_count = 0
        self.yellow_pikmin_count = 0
        self.blue_pikmin_count = 0
        self.previous_red_count = 0
        
        # Memory addresses
        self.red_pikmin_address = 0x803D6CF7
        self.yellow_pikmin_address = 0x803D6CF8  # Exemple
        self.blue_pikmin_address = 0x803D6CF9    # Exemple
        
        # Connection state
        self.dolphin_connected = False
        self.game_connected = False
        
        # Locations already checked
        self.checked_locations: Set[int] = set()
        
        # Monitoring task
        self.monitor_task = None
    
    async def server_auth(self, password_requested: bool = False):
        """Authenticate with server"""
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()
    
    async def connection_closed(self):
        """Handle connection closed"""
        if self.monitor_task:
            self.monitor_task.cancel()
        await super().connection_closed()
    
    async def connect_to_dolphin(self):
        """Connect to Dolphin emulator"""
        try:
            # Simulation de connexion à Dolphin
            # Dans un vrai projet, utilisez l'API Dolphin Memory Engine
            logger.info("Attempting to connect to Dolphin...")
            
            # Simuler une connexion réussie
            await asyncio.sleep(1)
            self.dolphin_connected = True
            self.game_connected = True
            
            logger.info("Successfully connected to Dolphin!")
            
            # Démarrer la surveillance
            if not self.monitor_task:
                self.monitor_task = asyncio.create_task(self.monitor_game_state())
                
        except Exception as e:
            logger.error(f"Failed to connect to Dolphin: {e}")
            self.dolphin_connected = False
            self.game_connected = False
    
    async def read_memory(self, address: int, size: int = 4) -> Optional[bytes]:
        """Read memory from Dolphin"""
        if not self.dolphin_connected:
            return None
        
        try:
            # Simulation de lecture mémoire
            # Dans un vrai projet, utilisez l'API Dolphin
            import random
            value = random.randint(0, 100)
            return struct.pack('>I', value)
            
        except Exception as e:
            logger.error(f"Memory read error at 0x{address:08X}: {e}")
            return None
    
    async def get_red_pikmin_count(self) -> int:
        """Get current red Pikmin count"""
        memory_data = await self.read_memory(self.red_pikmin_address, 4)
        if memory_data:
            return struct.unpack('>I', memory_data)[0]
        return 0
    
    async def check_pikmin_count(self):
        """Manually check Pikmin count"""
        if not self.game_connected:
            logger.warning("Game not connected")
            return
        
        count = await self.get_red_pikmin_count()
        logger.info(f"Current red Pikmin count: {count}")
    
    async def monitor_game_state(self):
        """Monitor game state for changes"""
        logger.info("Starting game state monitoring...")
        
        while self.game_connected:
            try:
                # Vérifier le nombre de Pikmin rouges
                current_red_count = await self.get_red_pikmin_count()
                
                if current_red_count != self.previous_red_count:
                    logger.info(f"Red Pikmin count changed: {self.previous_red_count} -> {current_red_count}")
                    self.red_pikmin_count = current_red_count
                    
                    # Vérifier les emplacements basés sur le nombre de Pikmin
                    await self.check_pikmin_locations()
                    
                    self.previous_red_count = current_red_count
                
                await asyncio.sleep(0.1)  # Vérifier toutes les 100ms
                
            except asyncio.CancelledError:
                logger.info("Game monitoring cancelled")
                break
            except Exception as e:
                logger.error(f"Error monitoring game state: {e}")
                await asyncio.sleep(1)
    
    async def check_pikmin_locations(self):
        """Check locations based on Pikmin count"""
        locations_to_check = []
        
        # Vérifier les emplacements basés sur le nombre de Pikmin rouges
        if self.red_pikmin_count >= 10:
            locations_to_check.append(11100)  # "Collect 10 Red Pikmin"
        if self.red_pikmin_count >= 25:
            locations_to_check.append(11101)  # "Collect 25 Red Pikmin"
        if self.red_pikmin_count >= 50:
            locations_to_check.append(11102)  # "Collect 50 Red Pikmin"
        if self.red_pikmin_count >= 100:
            locations_to_check.append(11103)  # "Collect 100 Red Pikmin"
        
        # Envoyer les emplacements vérifiés
        new_locations = [loc for loc in locations_to_check if loc not in self.checked_locations]
        if new_locations:
            self.checked_locations.update(new_locations)
            await self.send_msgs([{
                "cmd": "LocationChecks",
                "locations": new_locations
            }])
            logger.info(f"Checked locations: {new_locations}")
    
    def on_package(self, cmd: str, args: Dict[str, Any]):
        """Handle incoming packages"""
        if cmd == "Connected":
            self.game_state = ClientStatus.CLIENT_PLAYING
            logger.info("Connected to multiworld!")
            
            # Démarrer la connexion Dolphin si pas déjà fait
            if not self.dolphin_connected:
                asyncio.create_task(self.connect_to_dolphin())
                
        elif cmd == "ReceivedItems":
            # Traiter les items reçus
            start_index = args.get("index", 0)
            items = args.get("items", [])
            
            for i, item in enumerate(items):
                logger.info(f"Received item: {item}")
                # Ici, vous pourriez modifier l'état du jeu
                
        elif cmd == "LocationInfo":
            # Informations sur les emplacements
            locations = args.get("locations", [])
            logger.info(f"Location info: {locations}")

class PikminClient:
    """Main client class for Pikmin"""
    
    def __init__(self):
        self.ctx = None
    
    async def main(self, args):
        """Main client entry point"""
        self.ctx = PikminContext(args.connect, args.password)
        self.ctx.server_task = asyncio.create_task(server_loop(self.ctx))
        
        if gui_enabled:
            # Si GUI est activé, lancer l'interface graphique
            from kvui import GameManager
            
            class PikminManager(GameManager):
                logging_pairs = [
                    ("Client", "Archipelago"),
                    ("Pikmin", "Pikmin")
                ]
                base_title = "Archipelago Pikmin Client"
            
            await PikminManager(self.ctx).async_run()
        else:
            # Mode console
            await self.ctx.server_task

def launch():
    """Launch the Pikmin client"""
    import asyncio
    import argparse
    
    parser = argparse.ArgumentParser(description="Pikmin Client for Archipelago")
    parser.add_argument("--connect", default=None, help="Address of the multiworld host")
    parser.add_argument("--password", default=None, help="Password for the multiworld")
    
    args = parser.parse_args()
    
    client = PikminClient()
    asyncio.run(client.main(args))

if __name__ == "__main__":
    launch()