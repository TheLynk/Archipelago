#!/usr/bin/env python3
"""
Client Pikmin pour Archipelago
Connecte le jeu Pikmin au serveur Archipelago
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Set, Tuple
import subprocess
import os
from dataclasses import dataclass, field

from NetUtils import ClientCommandProcessor, CommonContext, server_loop
from CommonClient import ClientCommandProcessor as CCP, CommonContext as CC, get_base_parser, gui_enabled, logger, \
    server_loop
from Utils import async_start

# Configuration du jeu
GAME_NAME = "Pikmin"
SYSTEM_MESSAGE_TAG = "AP"

# Constantes pour les objets/lieux Pikmin
SHIP_PARTS = [
    "Main Engine", "Positron Generator", "Eternal Fuel Dynamo", "Interstellar Radio",
    "Bowsprit", "Chronos Reactor", "Gluon Drive", "Zirconium Rotor", "Automatic Gear",
    "Space Float", "Repair-type Bolt", "Shock Absorber", "Analog Computer",
    "Extraordinary Bolt", "Engine", "Whirlpool Generator", "Pilot's Seat",
    "Massage Girdle", "Radiation Canopy", "Gravity Jumper", "Sagittarius",
    "Geiger Counter", "Libra", "Nova Blaster", "Magnetic Flux Controller",
    "Chronos Reactor", "Anti-Dioxin Filter", "UV Lamp", "Secret Safe"
]

AREAS = [
    "The Impact Site", "The Forest of Hope", "The Forest Navel", 
    "The Distant Spring", "The Final Trial"
]

PIKMIN_TYPES = [
    "Red Pikmin", "Blue Pikmin", "Yellow Pikmin"
]

@dataclass
class PikminContext(CommonContext):
    """Context pour le client Pikmin"""
    game = GAME_NAME
    command_processor = None
    
    # État du jeu
    collected_parts: Set[str] = field(default_factory=set)
    current_area: Optional[str] = None
    current_day: int = 1
    pikmin_counts: Dict[str, int] = field(default_factory=lambda: {
        "Red Pikmin": 0,
        "Blue Pikmin": 0,
        "Yellow Pikmin": 0
    })
    
    # Connexion au jeu
    game_process: Optional[subprocess.Popen] = None
    memory_reader: Optional['MemoryReader'] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.command_processor = PikminCommandProcessor(self)


class PikminCommandProcessor(ClientCommandProcessor):
    """Processeur de commandes pour le client Pikmin"""
    
    def __init__(self, ctx: PikminContext):
        super().__init__(ctx)
        self.ctx = ctx
    
    def _cmd_status(self):
        """Affiche le statut actuel du jeu"""
        logger.info(f"Jour actuel: {self.ctx.current_day}")
        logger.info(f"Zone actuelle: {self.ctx.current_area}")
        logger.info(f"Pièces collectées: {len(self.ctx.collected_parts)}/30")
        logger.info(f"Pikmin: Rouge={self.ctx.pikmin_counts['Red Pikmin']}, "
                   f"Bleu={self.ctx.pikmin_counts['Blue Pikmin']}, "
                   f"Jaune={self.ctx.pikmin_counts['Yellow Pikmin']}")
    
    def _cmd_collect(self, part_name: str = ""):
        """Simule la collecte d'une pièce de vaisseau"""
        if not part_name:
            logger.info("Usage: !collect <nom_de_la_piece>")
            return
        
        if part_name in SHIP_PARTS:
            self.ctx.collected_parts.add(part_name)
            logger.info(f"Pièce collectée: {part_name}")
            # Notifier le serveur
            asyncio.create_task(self._send_location_check(part_name))
        else:
            logger.info(f"Pièce inconnue: {part_name}")
    
    async def _send_location_check(self, part_name: str):
        """Envoie un check de localisation au serveur"""
        if self.ctx.server and self.ctx.server.socket:
            location_id = hash(part_name) % (2**53)  # Génère un ID unique
            await self.ctx.send_msgs([{
                "cmd": "LocationChecks",
                "locations": [location_id]
            }])


class MemoryReader:
    """Classe pour lire la mémoire du jeu Pikmin"""
    
    def __init__(self, process: subprocess.Popen):
        self.process = process
        self.last_read_time = 0
        self.read_interval = 0.1  # Lire toutes les 100ms
    
    def read_game_state(self) -> Dict:
        """Lit l'état actuel du jeu depuis la mémoire"""
        current_time = time.time()
        if current_time - self.last_read_time < self.read_interval:
            return {}
        
        self.last_read_time = current_time
        
        # TODO: Implémentation de la lecture mémoire réelle
        # Ceci nécessiterait une analyse de la mémoire du jeu
        return {
            "current_day": 1,
            "current_area": "The Impact Site",
            "collected_parts": [],
            "pikmin_counts": {
                "Red Pikmin": 0,
                "Blue Pikmin": 0,
                "Yellow Pikmin": 0
            }
        }


class PikminClient:
    """Client principal pour Pikmin"""
    
    def __init__(self, server_address: str = "localhost", server_port: int = 38281):
        self.server_address = server_address
        self.server_port = server_port
        self.context = PikminContext(server_address, server_port)
        self.running = False
    
    async def start(self):
        """Démarre le client"""
        self.running = True
        logger.info("Démarrage du client Pikmin...")
        
        # Recherche du processus du jeu
        await self._find_game_process()
        
        # Boucle principale
        await self._main_loop()
    
    async def _find_game_process(self):
        """Recherche le processus du jeu Pikmin"""
        # TODO: Rechercher le processus réel du jeu
        # Pour l'instant, on simule
        logger.info("Recherche du processus Pikmin...")
        await asyncio.sleep(1)
        logger.info("Processus Pikmin trouvé (simulé)")
    
    async def _main_loop(self):
        """Boucle principale du client"""
        while self.running:
            try:
                # Lire l'état du jeu
                if self.context.memory_reader:
                    game_state = self.context.memory_reader.read_game_state()
                    await self._process_game_state(game_state)
                
                # Traitement des messages du serveur
                await self._process_server_messages()
                
                await asyncio.sleep(0.1)  # 100ms
                
            except Exception as e:
                logger.error(f"Erreur dans la boucle principale: {e}")
                await asyncio.sleep(1)
    
    async def _process_game_state(self, game_state: Dict):
        """Traite l'état du jeu reçu"""
        if not game_state:
            return
        
        # Vérifier les changements d'état
        if "current_day" in game_state:
            if game_state["current_day"] != self.context.current_day:
                self.context.current_day = game_state["current_day"]
                logger.info(f"Nouveau jour: {self.context.current_day}")
        
        if "current_area" in game_state:
            if game_state["current_area"] != self.context.current_area:
                self.context.current_area = game_state["current_area"]
                logger.info(f"Nouvelle zone: {self.context.current_area}")
        
        # Vérifier les nouvelles pièces collectées
        if "collected_parts" in game_state:
            new_parts = set(game_state["collected_parts"]) - self.context.collected_parts
            for part in new_parts:
                await self._on_part_collected(part)
    
    async def _on_part_collected(self, part_name: str):
        """Appelé quand une pièce est collectée"""
        self.context.collected_parts.add(part_name)
        logger.info(f"Pièce collectée: {part_name}")
        
        # Envoyer au serveur Archipelago
        if self.context.server and self.context.server.socket:
            location_id = hash(part_name) % (2**53)
            await self.context.send_msgs([{
                "cmd": "LocationChecks",
                "locations": [location_id]
            }])
    
    async def _process_server_messages(self):
        """Traite les messages du serveur"""
        # Cette méthode sera appelée par le CommonContext
        pass
    
    async def on_package(self, cmd: str, args: dict):
        """Traite les paquets reçus du serveur"""
        if cmd == "ReceivedItems":
            await self._handle_received_items(args)
        elif cmd == "LocationInfo":
            await self._handle_location_info(args)
    
    async def _handle_received_items(self, args: dict):
        """Traite les objets reçus du serveur"""
        items = args.get("items", [])
        for item in items:
            item_name = item.get("item", "")
            player_name = item.get("player", "")
            logger.info(f"Objet reçu: {item_name} de {player_name}")
            
            # TODO: Donner l'objet au joueur dans le jeu
            await self._give_item_to_player(item_name)
    
    async def _give_item_to_player(self, item_name: str):
        """Donne un objet au joueur dans le jeu"""
        # TODO: Implémentation pour modifier la mémoire du jeu
        logger.info(f"Donner l'objet au joueur: {item_name}")
    
    async def _handle_location_info(self, args: dict):
        """Traite les informations de localisation"""
        locations = args.get("locations", [])
        for location in locations:
            logger.info(f"Info de localisation: {location}")


def create_pikmin_parser():
    """Crée le parser d'arguments pour le client Pikmin"""
    parser = get_base_parser(description="Client Pikmin pour Archipelago")
    parser.add_argument('--game-path', type=str, help='Chemin vers le jeu Pikmin')
    return parser


async def main():
    """Fonction principale"""
    parser = create_pikmin_parser()
    args = parser.parse_args()
    
    # Créer et démarrer le client
    client = PikminClient(args.connect, args.port)
    
    try:
        await client.start()
    except KeyboardInterrupt:
        logger.info("Arrêt du client...")
        client.running = False


if __name__ == "__main__":
    if gui_enabled:
        # TODO: Implémenter l'interface graphique
        logger.info("Interface graphique non implémentée")
    else:
        asyncio.run(main())