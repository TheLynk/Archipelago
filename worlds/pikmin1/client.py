"""
Client Pikmin 1 GameCube PAL pour Archipelago
Ce client se connecte au jeu via Dolphin et lit la mémoire
"""

import asyncio
import logging
import struct
import time
from typing import Dict, List, Optional, Set, Tuple

from CommonClient import CommonContext, server_loop, ClientCommandProcessor, logger, gui_enabled
from NetUtils import ClientStatus, color
from Utils import async_start

if gui_enabled:
    from kivy.app import App
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from kivy.uix.textinput import TextInput
    from kivy.uix.button import Button


class PikminClientCommandProcessor(ClientCommandProcessor):
    """Processeur de commandes pour le client Pikmin"""
    
    def _cmd_dolphin(self):
        """Commande pour se connecter à Dolphin"""
        if self.ctx.dolphin_sync_task:
            logger.info("Dolphin déjà connecté")
        else:
            self.ctx.dolphin_sync_task = asyncio.create_task(self.ctx.dolphin_sync())
            logger.info("Tentative de connexion à Dolphin...")


class PikminContext(CommonContext):
    """Context pour le client Pikmin"""
    
    command_processor = PikminClientCommandProcessor
    game = "Pikmin"
    items_handling = 0b111  # Recevoir tous les items
    
    def __init__(self, server_address, password):
        super().__init__(server_address, password)
        
        # Variables pour Dolphin
        self.dolphin_sync_task = None
        self.dolphin_process = None
        self.dolphin_pid = None
        
        # Variables de jeu
        self.red_pikmin_count = 0
        self.last_red_pikmin_count = 0
        self.red_pikmin_address = 0x803D6CF7
        
        # Locations vérifiées
        self.checked_locations: Set[int] = set()
        
    async def server_auth(self, password_requested: bool = False):
        """Authentification avec le serveur"""
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()
        
    async def connection_closed(self):
        """Gestion de la fermeture de connexion"""
        if self.dolphin_sync_task:
            self.dolphin_sync_task.cancel()
            self.dolphin_sync_task = None
        await super().connection_closed()
        
    @property
    def endpoints(self):
        """Points de terminaison pour la connexion"""
        if self.server_task is None:
            return []
        return [self.server_task]
        
    async def shutdown(self):
        """Arrêt du client"""
        if self.dolphin_sync_task:
            self.dolphin_sync_task.cancel()
            self.dolphin_sync_task = None
        await super().shutdown()
        
    def on_package(self, cmd: str, args: dict):
        """Traitement des paquets reçus"""
        if cmd in {"Connected"}:
            self.slot_data = args.get("slot_data", {})
            self.red_pikmin_address = self.slot_data.get("red_pikmin_address", 0x803D6CF7)
            logger.info(f"Connecté! Adresse pikmin rouge: 0x{self.red_pikmin_address:08X}")
            
        elif cmd in {"ReceivedItems"}:
            start_index = args["index"]
            
            if start_index == 0:
                self.items_received = []
                
            for item in args["items"]:
                self.items_received.append(item)
                logger.info(f"Reçu: {self.item_names[item.item]} de {self.player_names[item.player]}")
                
    async def dolphin_sync(self):
        """Synchronisation avec Dolphin"""
        logger.info("Démarrage de la synchronisation Dolphin...")
        
        while True:
            try:
                # Tentative de connexion à Dolphin
                if not self.dolphin_process:
                    await self.connect_to_dolphin()
                
                if self.dolphin_process:
                    # Lire la mémoire
                    await self.read_memory()
                    
                    # Vérifier les conditions de location
                    await self.check_locations()
                    
                await asyncio.sleep(1)  # Vérifier chaque seconde
                
            except Exception as e:
                logger.error(f"Erreur dans dolphin_sync: {e}")
                await asyncio.sleep(5)  # Attendre avant de réessayer
                
    async def connect_to_dolphin(self):
        """Se connecter au processus Dolphin"""
        try:
            import psutil
            
            # Chercher le processus Dolphin
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] and 'dolphin' in proc.info['name'].lower():
                    self.dolphin_process = proc
                    self.dolphin_pid = proc.info['pid']
                    logger.info(f"Connecté à Dolphin (PID: {self.dolphin_pid})")
                    return
                    
            logger.warning("Dolphin non trouvé")
            
        except ImportError:
            logger.error("psutil requis pour la connexion Dolphin")
        except Exception as e:
            logger.error(f"Erreur de connexion à Dolphin: {e}")
            
    async def read_memory(self):
        """Lire la mémoire de Dolphin"""
        try:
            # Ici, vous devrez implémenter la lecture mémoire réelle
            # Pour l'instant, simulation avec une valeur qui augmente
            import random
            
            # Simulation: augmenter parfois le nombre de pikmin
            if random.random() < 0.1:  # 10% de chance d'augmenter
                self.red_pikmin_count = min(self.red_pikmin_count + 1, 100)
                
            # En vrai, vous feriez quelque chose comme:
            # memory_value = read_dolphin_memory(self.red_pikmin_address)
            # self.red_pikmin_count = memory_value
            
        except Exception as e:
            logger.error(f"Erreur de lecture mémoire: {e}")
            
    async def check_locations(self):
        """Vérifier les conditions de location"""
        try:
            # Vérifier si on a 10 pikmin rouge
            if self.red_pikmin_count >= 10 and self.last_red_pikmin_count < 10:
                location_id = 0x1000001  # ID de "10 Red Pikmin"
                
                if location_id not in self.checked_locations:
                    self.checked_locations.add(location_id)
                    await self.send_msgs([{
                        "cmd": "LocationChecks",
                        "locations": [location_id]
                    }])
                    logger.info(f"Location '10 Red Pikmin' déclenchée! ({self.red_pikmin_count} pikmin)")
                    
            self.last_red_pikmin_count = self.red_pikmin_count
            
        except Exception as e:
            logger.error(f"Erreur dans check_locations: {e}")


def launch():
    """Lancer le client"""
    async def main():
        parser = get_base_parser(description="Client Pikmin 1 GameCube PAL pour Archipelago")
        args, rest = parser.parse_known_args()
        
        ctx = PikminContext(args.connect, args.password)
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
        
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        
        await ctx.server_task
        
    import colorama
    colorama.init()
    asyncio.run(main())


def get_base_parser(description=None):
    """Obtenir le parser de base"""
    import argparse
    
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--connect', default=None, help='Adresse pour se connecter')
    parser.add_argument('--password', default=None, help='Mot de passe si nécessaire')
    
    return parser


if __name__ == '__main__':
    launch()