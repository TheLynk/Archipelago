"""
Module pour lire la mémoire de Dolphin
Spécifique à Pikmin 1 GameCube PAL
"""

import ctypes
import logging
import struct
import sys
from typing import Optional, Union

logger = logging.getLogger(__name__)

# Constantes pour Windows
if sys.platform == "win32":
    from ctypes import wintypes
    
    # Droits d'accès processus
    PROCESS_VM_READ = 0x0010
    PROCESS_QUERY_INFORMATION = 0x0400
    
    # Bibliothèques Windows
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    
    kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    kernel32.ReadProcessMemory.restype = wintypes.BOOL
    
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL


class DolphinMemoryReader:
    """Lecteur de mémoire pour Dolphin"""
    
    def __init__(self, pid: int):
        self.pid = pid
        self.process_handle = None
        self.base_address = None
        self.mem1_base = 0x80000000  # Adresse de base de la mémoire GameCube
        
    def connect(self) -> bool:
        """Se connecter au processus Dolphin"""
        try:
            if sys.platform == "win32":
                self.process_handle = kernel32.OpenProcess(
                    PROCESS_VM_READ | PROCESS_QUERY_INFORMATION,
                    False,
                    self.pid
                )
                
                if not self.process_handle:
                    logger.error(f"Impossible d'ouvrir le processus {self.pid}")
                    return False
                    
                # Trouver l'adresse de base de la mémoire GameCube
                self.base_address = self._find_mem1_base()
                if not self.base_address:
                    logger.error("Impossible de trouver l'adresse de base MEM1")
                    return False
                    
                logger.info(f"Connecté au processus {self.pid}, base: 0x{self.base_address:08X}")
                return True
                
            else:
                logger.error("Plateforme non supportée pour la lecture mémoire")
                return False
                
        except Exception as e:
            logger.error(f"Erreur de connexion: {e}")
            return False
            
    def _find_mem1_base(self) -> Optional[int]:
        """Trouver l'adresse de base de MEM1 dans Dolphin"""
        try:
            import psutil
            
            # Cette méthode est simplifiée - en réalité, vous devriez
            # scanner la mémoire pour trouver la bonne adresse
            # Pour l'instant, retournons une adresse simulée
            return 0x10000000  # Adresse exemple
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de MEM1: {e}")
            return None
            
    def read_memory(self, address: int, size: int) -> Optional[bytes]:
        """Lire la mémoire à l'adresse spécifiée"""
        if not self.process_handle or not self.base_address:
            return None
            
        try:
            # Convertir l'adresse GameCube en adresse Dolphin
            dolphin_address = self.base_address + (address - self.mem1_base)
            
            if sys.platform == "win32":
                buffer = ctypes.create_string_buffer(size)
                bytes_read = ctypes.c_size_t(0)
                
                success = kernel32.ReadProcessMemory(
                    self.process_handle,
                    dolphin_address,
                    buffer,
                    size,
                    ctypes.byref(bytes_read)
                )
                
                if success and bytes_read.value == size:
                    return buffer.raw
                else:
                    logger.warning(f"Lecture partielle: {bytes_read.value}/{size} bytes")
                    return None
                    
            return None
            
        except Exception as e:
            logger.error(f"Erreur de lecture mémoire à 0x{address:08X}: {e}")
            return None
            
    def read_u8(self, address: int) -> Optional[int]:
        """Lire un entier 8-bit non signé"""
        data = self.read_memory(address, 1)
        if data:
            return struct.unpack(">B", data)[0]  # Big-endian
        return None
        
    def read_u16(self, address: int) -> Optional[int]:
        """Lire un entier 16-bit non signé"""
        data = self.read_memory(address, 2)
        if data:
            return struct.unpack(">H", data)[0]  # Big-endian
        return None
        
    def read_u32(self, address: int) -> Optional[int]:
        """Lire un entier 32-bit non signé"""
        data = self.read_memory(address, 4)
        if data:
            return struct.unpack(">I", data)[0]  # Big-endian
        return None
        
    def read_float(self, address: int) -> Optional[float]:
        """Lire un float 32-bit"""
        data = self.read_memory(address, 4)
        if data:
            return struct.unpack(">f", data)[0]  # Big-endian
        return None
        
    def disconnect(self):
        """Déconnecter du processus"""
        if self.process_handle and sys.platform == "win32":
            kernel32.CloseHandle(self.process_handle)
            self.process_handle = None
            logger.info("Déconnecté du processus Dolphin")


class PikminMemoryReader:
    """Lecteur spécialisé pour Pikmin 1 GameCube PAL"""
    
    # Adresses mémoire pour Pikmin 1 GameCube PAL
    ADDRESSES = {
        "red_pikmin_count": 0x803D6CF7,
        "yellow_pikmin_count": 0x803D6CF8,  # Exemple
        "blue_pikmin_count": 0x803D6CF9,    # Exemple
        "player_x": 0x803D6D00,             # Exemple
        "player_y": 0x803D6D04,             # Exemple
        "player_z": 0x803D6D08,             # Exemple
        "day_counter": 0x803D6D10,          # Exemple
        "ship_parts": 0x803D6D20,           # Exemple
    }
    
    def __init__(self, dolphin_reader: DolphinMemoryReader):
        self.dolphin_reader = dolphin_reader
        
    def get_red_pikmin_count(self) -> Optional[int]:
        """Obtenir le nombre de pikmin rouge"""
        return self.dolphin_reader.read_u8(self.ADDRESSES["red_pikmin_count"])
        
    def get_yellow_pikmin_count(self) -> Optional[int]:
        """Obtenir le nombre de pikmin jaunes"""
        return self.dolphin_reader.read_u8(self.ADDRESSES["yellow_pikmin_count"])
        
    def get_blue_pikmin_count(self) -> Optional[int]:
        """Obtenir le nombre de pikmin bleus"""
        return self.dolphin_reader.read_u8(self.ADDRESSES["blue_pikmin_count"])
        
    def get_player_position(self) -> Optional[tuple]:
        """Obtenir la position du joueur (x, y, z)"""
        x = self.dolphin_reader.read_float(self.ADDRESSES["player_x"])
        y = self.dolphin_reader.read_float(self.ADDRESSES["player_y"])
        z = self.dolphin_reader.read_float(self.ADDRESSES["player_z"])
        
        if x is not None and y is not None and z is not None:
            return (x, y, z)
        return None
        
    def get_day_counter(self) -> Optional[int]:
        """Obtenir le compteur de jours"""
        return self.dolphin_reader.read_u32(self.ADDRESSES["day_counter"])
        
    def get_ship_parts_collected(self) -> Optional[int]:
        """Obtenir le nombre de pièces de vaisseau collectées"""
        return self.dolphin_reader.read_u32(self.ADDRESSES["ship_parts"])
        
    def get_game_state(self) -> dict:
        """Obtenir l'état complet du jeu"""
        return {
            "red_pikmin": self.get_red_pikmin_count(),
            "yellow_pikmin": self.get_yellow_pikmin_count(),
            "blue_pikmin": self.get_blue_pikmin_count(),
            "player_position": self.get_player_position(),
            "day": self.get_day_counter(),
            "ship_parts": self.get_ship_parts_collected(),
        }


def find_dolphin_process() -> Optional[int]:
    """Trouver le PID du processus Dolphin"""
    try:
        import psutil
        
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and 'dolphin' in proc.info['name'].lower():
                return proc.info['pid']
                
        return None
        
    except ImportError:
        logger.error("psutil requis pour trouver Dolphin")
        return None
    except Exception as e:
        logger.error(f"Erreur lors de la recherche de Dolphin: {e}")
        return None


# Exemple d'utilisation
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Trouver Dolphin
    dolphin_pid = find_dolphin_process()
    if not dolphin_pid:
        logger.error("Dolphin non trouvé")
        sys.exit(1)
        
    # Créer le lecteur
    dolphin_reader = DolphinMemoryReader(dolphin_pid)
    if not dolphin_reader.connect():
        logger.error("Impossible de se connecter à Dolphin")
        sys.exit(1)
        
    # Créer le lecteur Pikmin
    pikmin_reader = PikminMemoryReader(dolphin_reader)
    
    # Lire les données
    try:
        while True:
            import time
            
            state = pikmin_reader.get_game_state()
            logger.info(f"État du jeu: {state}")
            
            if state["red_pikmin"] is not None and state["red_pikmin"] >= 10:
                logger.info("Condition '10 Red Pikmin' remplie!")
                
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Arrêt demandé")
    finally:
        dolphin_reader.disconnect()