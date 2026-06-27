import asyncio
import os
import struct
import time
from typing import TYPE_CHECKING, Optional

import dolphin_memory_engine as dme

import Utils
from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus
from .P1UI import P1UI
from .P1Data import *

if TYPE_CHECKING:
    import kvui

SCOUT_RETRY_INTERVAL = 5.0  # seconds between scout retries

UNLOCKED_AREAS: MemoryAddress = mem(0x803A2803, 0x8039D983)  # byte
COUNT_TOTAL_PARTS: MemoryAddress = mem(0x812427FF, 0x81249DE7)  # byte
COUNT_REQUIRED_PARTS: MemoryAddress = mem(0x81242803, 0x81249DEB)  # byte
TIME_HOURS: MemoryAddress = mem(0x803A2930, 0x803A2930)  # int, 7=morning, >=19=end of day
DAY_NUMBER: MemoryAddress = mem(0x803A2937, 0x803A2937)  # byte, current day number

# Ship part hint text address (PAL) — universal for all parts
SHIP_PART_TEXT_ADDR = 0x807B100A
SHIP_PART_TEXT_LENGTH = 313  # 0x807B1143 - 0x807B100A
LANG_NAMES = {"en": "English", "fr": "Français", "de": "Deutsch", "it": "Italiano", "es": "Español"}

LANG_MSG_DETECTED = {
    "en": "Language detected",
    "fr": "Langue détectée",
    "de": "Sprache erkannt",
    "it": "Lingua rilevata",
    "es": "Idioma detectado",
}

LANG_MSG_LOCKED = {
    "en": "Language locked",
    "fr": "Langue verrouillée",
    "de": "Sprache gesperrt",
    "it": "Lingua bloccata",
    "es": "Idioma bloqueado",
}

# Language detection — two addresses must both match the same language string.
# Only checked while DAY_NUMBER == 0 (title/loading screen).
# Order: (addr_a, addr_b, language_bytes, language_name)
LANGUAGE_DETECT_TABLE = [
    (0x804E8640, 0x804E8788, b"English",    "en"),
    (0x804E8A40, 0x804E8B90, b"Fran\xe7ais", "fr"),
    (0x804E8CC0, 0x804E90A0, b"Deutsch",    "de"),
    (0x804E8F10, 0x804E92F0, b"Italiano",   "it"),
    (0x804E8E58, 0x804E9238, b"Espa\xf1ol", "es"),
]

# Official in-game ship part names per language.
# Key = English name (as used in ALL_PARTS), value = dict lang -> bytes (latin-1).
# Order in list: fr, de, it, es
SHIP_PART_TRANSLATIONS: dict[str, dict[str, bytes]] = {
    "Main Engine":         {"fr": b"Moteur Principal",       "de": b"Hauptantrieb des Dolphins", "it": b"Motore principale",    "es": b"Motor principal del Dolphin"},
    "Positron Generator":  {"fr": b"Positronator",           "de": b"Positron-Generator",        "it": b"Generat. positroni",    "es": b"Positronador"},
    "Eternal Fuel Dynamo": {"fr": b"G\xe9n\xe9rateur Infini","de": b"Kraftstoff-Dynamo",          "it": b"Dinamo perenne",        "es": b"Dinamo"},
    "Extraordinary Bolt":  {"fr": b"Super Boulon",           "de": b"Au\xdfergwl. Schraube",     "it": b"Vite straordinaria",    "es": b"Perno de aleci\xf3n"},
    "Whimsical Radar":     {"fr": b"Radar Bizarre",          "de": b"Sonderbar-Radar",           "it": b"Super radar",           "es": b"Radar Enigm\xe1tico"},
    "Geiger Counter":      {"fr": b"Compteur Geiger",        "de": b"Geigenz\xe4hler",           "it": b"Contatore Geiger",      "es": b"Contador Geiger"},
    "Radiation Canopy":    {"fr": b"Cockpit NBC",            "de": b"Strahlenschutz",            "it": b"Calotta radiazioni",    "es": b"C\xe1psula protectora"},
    "Sagittarius":         {"fr": b"Sagittaire",             "de": b"Der Sch\xfctze",            "it": b"Sagittario",            "es": b"Sagitario"},
    "Shock Absorber":      {"fr": b"Absorbeur de Choc",      "de": b"Sto\xdfd\xe4mpfer",         "it": b"Assorbishock",          "es": b"Amortiguador"},
    "Automatic Gear":      {"fr": b"Bo\xeete Automatique",   "de": b"Autom. Getriebe",           "it": b"Autonavigatore",        "es": b"Transmisi\xf3n"},
    "#1 Ionium Jet":       {"fr": b"Propulseur 1",           "de": b"Ionenjet Nr.1",             "it": b"Jet ionio 1",           "es": b"Reactor I\xf3nico n.\xb0 1"},
    "Anti-Dioxin Filter":  {"fr": b"Filtre \xe0 Dioxine",   "de": b"Dioxin-Filter",             "it": b"Anti diossina",         "es": b"Filtro anti-dioxinas"},
    "Omega Stabilizer":    {"fr": b"Stabilisateur Om\xe9ga", "de": b"Omega-Stabilisator",        "it": b"Stabilizzat. omega",    "es": b"Estabilizador Omega"},
    "Gravity Jumper":      {"fr": b"Unit\xe9 Antigrav",      "de": b"Gravitationsblocker",       "it": b"Propulsore gravit\xe0",  "es": b"Anti-gravitador"},
    "Analog Computer":     {"fr": b"Intelligence Artificielle", "de": b"Analoger Computer",      "it": b"Computer analogico",    "es": b"Sistema Anal\xf3gico"},
    "Guard Satellite":     {"fr": b"Satellite de Garde",     "de": b"W\xe4chter-Satellit",       "it": b"Satellite guardia",     "es": b"Sat\xe9lite"},
    "Libra":               {"fr": b"Balance",                "de": b"Die Waage",                 "it": b"Bilancia",              "es": b"Libra"},
    "Repair-Type Bolt":    {"fr": b"Boulon de Secours",      "de": b"Reparatur-Bolzen",          "it": b"Bullone riparazione",   "es": b"Perno reparador"},
    "Gluon Drive":         {"fr": b"Unit\xe9 Gluonique",     "de": b"Gluon-Antrieb",             "it": b"Unit\xe0 a gluoni",     "es": b"Emisor de gluones"},
    "Zirconium Rotor":     {"fr": b"Rotor Zirconium",        "de": b"Zirkonium-Rotor",           "it": b"Rotore zirconio",       "es": b"Rotor de zirconio"},
    "Interstellar Radio":  {"fr": b"Radio Stellaire",        "de": b"Interstellar-Radio",        "it": b"Radio interstellare",   "es": b"Radio interestelar"},
    "Pilot's Seat":        {"fr": b"Si\xe8ge du Pilote",     "de": b"Pilotensitz",               "it": b"Sedile pilota",         "es": b"Asiento de piloto"},
    "#2 Ionium Jet":       {"fr": b"Propulseur 2",           "de": b"Ionenjet Nr.2",             "it": b"Jet ionio 2",           "es": b"Reactor I\xf3nico n.\xb0 2"},
    "Bowsprit":            {"fr": b"Beaupr\xe9",             "de": b"Bugspriet",                 "it": b"Bompresso",             "es": b"Baupr\xe9s"},
    "Chronos Reactor":     {"fr": b"R\xe9acteur Chronos",    "de": b"Kr\xfcmmungsreaktor",       "it": b"Cronoreattore",         "es": b"Reactor Chronos"},
    "Nova Blaster":        {"fr": b"Missile Nova",           "de": b"Nova-Blaster",              "it": b"Polverizzatore",        "es": b"Detonador Nova"},
    "Space Float":         {"fr": b"Bou\xe9e Spatiale",      "de": b"Levita-Reifen",             "it": b"Galleggiante",          "es": b"Flotador espacial"},
    "Massage Machine":     {"fr": b"Si\xe8ge de Massage",    "de": b"Massageeinheit",            "it": b"Macchina massaggi",     "es": b"M\xe1quina de masajes"},
    "UV Lamp":             {"fr": b"Lampe \xe0 UV",          "de": b"UV-Lampe",                  "it": b"Lampada UV",            "es": b"L\xe1mpara de UV"},
    "Secret Safe":         {"fr": b"Coffre Secret",          "de": b"Geheimsafe",                "it": b"Cassaforte",            "es": b"Caja fuerte"},
}


# Pikmin count addresses — used for location checking (stable, always valid)
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

PIKMIN_ADDRESSES = {
    b"GPIP01": PIKMIN_ADDRESSES_PAL,
    b"GPIE01": PIKMIN_ADDRESSES_NTSC_U,
}

# Onion active counts — written by the patched DOL stub to fixed addresses.
# VAL: current onion count (mirror of dynamic address)
ONION_VAL_ADDRS_PAL = {
    "red":    0x803D7000,
    "yellow": 0x803D7004,
    "blue":   0x803D7008,
}
ONION_VAL_ADDRS = {b"GPIP01": ONION_VAL_ADDRS_PAL}

# Dynamic onion RAM — total pikmin per color (all stages combined), stable PAL.
# Zeroed until the first day is loaded; transitions 0->nonzero = onion loaded.
# Confirmed in DME: 0x803D6D20=Blue, 0x803D6D24=Red, 0x803D6D28=Yellow.
ONION_DYN_ADDRS_PAL: dict[str, int] = {
    "red":    0x803D6D24,
    "yellow": 0x803D6D28,
    "blue":   0x803D6D20,
}
ONION_DYN_ADDRS = {b"GPIP01": ONION_DYN_ADDRS_PAL}

# Sentinel: address watched to detect day-start (0 -> nonzero transition).
# 0x803A2924 = 0 on the day-selection menu, nonzero once the day starts.
# Reliable for detecting each new day (not just the first one).
ONION_DYN_SENTINEL_PAL = 0x803A2924
ONION_DYN_SENTINEL = {b"GPIP01": ONION_DYN_SENTINEL_PAL}

# Persistent pikmin counts per stage (u32 each).
# The game recalculates the displayed total as Leaf + Bud + Flower automatically.
# These are the REAL addresses confirmed in DME (PAL GP1P01).
ONION_STAGE_ADDRS_CLIENT_PAL: dict[str, dict[str, int]] = {
    "red": {
        "leaf":   0x803D6C7C,
        "bud":    0x803D6C80,
        "flower": 0x803D6C84,
    },
    "yellow": {
        "leaf":   0x803D6C88,
        "bud":    0x803D6C8C,
        "flower": 0x803D6C90,
    },
    "blue": {
        "leaf":   0x803D6C70,
        "bud":    0x803D6C74,
        "flower": 0x803D6C78,
    },
}
ONION_STAGE_ADDRS_CLIENT = {b"GPIP01": ONION_STAGE_ADDRS_CLIENT_PAL}


class P1CommandProcessor(ClientCommandProcessor):
    def __init__(self, ctx: CommonContext):
        super().__init__(ctx)

    def _cmd_debughint(self) -> bool:
        """Toggle debug logging for hint-related messages."""
        self.ctx.debug_hint = not getattr(self.ctx, "debug_hint", False)
        state = "ON" if self.ctx.debug_hint else "OFF"
        logger.info(f"[DEBUG] Hint debug: {state}")
        if self.ctx.debug_hint:
            slot_data = getattr(self.ctx, "slot_data", {}) or {}
            hint_mode = slot_data.get("ship_part_hint_mode", 0)
            hints = slot_data.get("hints", {})
            logger.info(f"[DEBUG HINT] Hint mode: {hint_mode}")
            logger.info(f"[DEBUG HINT] Hints count: {len(hints)}")
            if hints:
                for part_name, hint_data in hints.items():
                    logger.info(f"[DEBUG HINT]   {part_name}: {hint_data.get('Item', '?')} at {hint_data.get('Location', '?')}")
        return True

    def _cmd_debugdays(self) -> bool:
        """Toggle debug logging for day cycle messages."""
        self.ctx.debug_days = not getattr(self.ctx, "debug_days", False)
        state = "ON" if self.ctx.debug_days else "OFF"
        logger.info(f"[DEBUG] Day cycle debug: {state}")
        if self.ctx.debug_days:
            slot_data = getattr(self.ctx, "slot_data", {}) or {}
            mode = slot_data.get("day_cycle_mode", 0)
            logger.info(f"[DEBUG DAYS] Day cycle mode: {mode}")
        return True

    def _cmd_debugpbonus(self) -> bool:
        """Toggle debug logging for Pikmin bonus item messages."""
        self.ctx.debug_pbonus = not getattr(self.ctx, "debug_pbonus", False)
        state = "ON" if self.ctx.debug_pbonus else "OFF"
        logger.info(f"[DEBUG] Pikmin bonus debug: {state}")
        if self.ctx.debug_pbonus:
            logger.info(f"[DEBUG PBONUS] Applied items: {getattr(self.ctx, 'pikmin_items_applied', {})}")
            logger.info(f"[DEBUG PBONUS] Pending DYN: {getattr(self.ctx, 'pikmin_dyn_pending', {})}")
        return True

    def _cmd_debuglangue(self) -> bool:
        """Affiche la langue actuellement détectée par le client."""
        lang      = getattr(self.ctx, "detected_language", "en")
        confirmed = getattr(self.ctx, "_language_confirmed", False)

        status = "verrouillée (en jeu)" if confirmed else "en cours de détection (menu principal)"
        logger.info(f"[DEBUG LANGUE] Langue : {LANG_NAMES.get(lang, lang)} ({lang}) — {status}")

        if dme.is_hooked():
            try:
                day_number = struct.unpack(">B", dme.read_bytes(0x803A2937, 1))[0]
                logger.info(f"[DEBUG LANGUE] DAY_NUMBER = {day_number} ({'menu principal' if day_number == 0 else 'en jeu — détection arrêtée'})")
            except Exception as e:
                logger.info(f"[DEBUG LANGUE] DAY_NUMBER illisible : {e}")

            logger.info("[DEBUG LANGUE] Lecture live des adresses de détection :")
            for addr_a, addr_b, lang_bytes, lang_code in LANGUAGE_DETECT_TABLE:
                try:
                    val_a = dme.read_bytes(addr_a, len(lang_bytes))
                    val_b = dme.read_bytes(addr_b, len(lang_bytes))
                    match = "✓" if val_a == lang_bytes and val_b == lang_bytes else "✗"
                    logger.info(f"  {match} {LANG_NAMES.get(lang_code, lang_code):10s} | 0x{addr_a:08X}={val_a!r}  0x{addr_b:08X}={val_b!r}")
                except Exception as e:
                    logger.info(f"  ? {LANG_NAMES.get(lang_code, lang_code):10s} | erreur lecture : {e}")
        else:
            logger.info("[DEBUG LANGUE] Dolphin non connecté — lecture live impossible.")
        return True

    def _cmd_updatelanguage(self) -> bool:
        """Only use this command on the game's title screen to properly update the Pikmin client language detection."""
        if not dme.is_hooked():
            logger.warning("[UpdateLanguage] Not connected to Dolphin.")
            return False
        try:
            dme.write_bytes(DAY_NUMBER[b"GPIP01"], bytes([0]))
            self.ctx._language_confirmed = False
            self.ctx.detected_language = "en"
            logger.info("[UpdateLanguage] DAY_NUMBER reset to 0 — language detection restarted.")
        except Exception as e:
            logger.error(f"[UpdateLanguage] Failed to reset DAY_NUMBER: {e}")
        return True
        """Scan RAM from 0x80000000 to 0x80003000 and write results to scancavelog.txt
        in the same folder as the patched ISO."""
        import threading

        def _do_scan():
            SCAN_START = 0x80000000
            SCAN_END   = 0x80003000
            CHUNK_SIZE = 0x100

            # Resolve output directory: same folder as patched ISO
            try:
                from settings import get_settings
                options = get_settings()
                iso_path = options.get("pikmin_options", {}).get("iso_file", "")
                if iso_path and os.path.isfile(iso_path):
                    out_dir = os.path.dirname(os.path.abspath(iso_path))
                else:
                    out_dir = os.getcwd()
            except Exception:
                out_dir = os.getcwd()

            out_path = os.path.join(out_dir, "scancavelog.txt")
            logger.info(f"[scancave] Scanning 0x{SCAN_START:08X}–0x{SCAN_END:08X} → {out_path}")

            try:
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(f"Pikmin 1 RAM scan: 0x{SCAN_START:08X} – 0x{SCAN_END:08X}\n")
                    f.write("=" * 60 + "\n\n")
                    addr = SCAN_START
                    while addr < SCAN_END:
                        size = min(CHUNK_SIZE, SCAN_END - addr)
                        try:
                            chunk = dme.read_bytes(addr, size)
                        except Exception as e:
                            f.write(f"0x{addr:08X}: <read error: {e}>\n")
                            addr += size
                            continue

                        for row_off in range(0, size, 16):
                            row_addr = addr + row_off
                            row = chunk[row_off:row_off + 16]
                            hex_part  = " ".join(f"{b:02X}" for b in row)
                            ascii_part = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in row)
                            f.write(f"0x{row_addr:08X}  {hex_part:<47}  {ascii_part}\n")

                        addr += size

                logger.info(f"[scancave] Done. Log written to: {out_path}")
            except Exception as e:
                logger.error(f"[scancave] Failed to write log: {e}")

        if not dme.is_hooked():
            logger.warning("[scancave] Not connected to Dolphin.")
            return False

        threading.Thread(target=_do_scan, daemon=True, name="scancave").start()
        logger.info("[scancave] Scan started in background...")
        return True
        """Re-apply all received Pikmin bonus items and re-check all collected ship part locations.
        Use this if the game crashed and you lost progress."""
        old_key = self.ctx._save_key()

        # Reset applied items so all bonuses get re-applied
        self.ctx.pikmin_items_applied = {}
        self.ctx.save_applied()

        new_key = self.ctx._save_key()

        # Remove ship part location IDs from checked_locations so they get re-checked
        ship_part_location_ids = {data.ap_id for data in ALL_PARTS.values()}
        self.ctx.locations_checked -= ship_part_location_ids

        logger.info(f"Crash recovery: old key = '{old_key}'")
        logger.info(f"Crash recovery: new key = '{new_key}'")
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
        # Debug mode toggles (via /debughint, /debugdays, /debugpbonus)
        self.debug_mode: bool = False  # kept for legacy internal checks
        self.debug_hint: bool = False
        self.debug_days: bool = False
        self.debug_pbonus: bool = False
        # Tracks whether the dynamic onion sentinel was zero last tick.
        # Used to detect the 0->nonzero transition = onion freshly loaded for new day.
        self._onion_dyn_was_zero: bool = True
        # Cached base address of the Red onion dynamic structure (found by RAM scan).
        # Reset to None at each day-start before re-scanning.
        self._dyn_base_red: int | None = None
        # Ship part hint tracking
        self.last_hint_shown: str = ""
        # Raw bytes of the hint we wrote, so we can re-apply if the game overwrites it
        self.last_hint_bytes: bytes = b""
        # Throttle for day cycle debug logs (timestamp of last log)
        self._last_day_debug_log: float = 0.0
        # Throttle for NTSC warning (timestamp of last warning)
        self._last_ntsc_warning: float = 0.0
        # Scouted locations: loc_id -> {"item_name": str, "player": int}
        self.scouted_locations: dict[int, dict] = {}
        # Flag to trigger location scout after connection is fully established
        self.needs_location_scout: bool = False
        # Track scout state for retry logic
        self.scout_sent: bool = False
        self.scout_sent_time: float = 0.0
        self.scout_received: bool = False
        # Track which location hints have been created on the server
        self.created_hints: set[int] = set()
        # Super Radar: cache of ALL scouted locations (not just own)
        self.all_locations_scouted: dict[int, dict] = {}
        # Super Radar: track that we've requested all-locations scout
        self.super_radar_requested: bool = False
        self.super_radar_hints_created: bool = False
        # Super Radar: store hints received from server
        self.server_hints: dict[int, dict] = {}
        # Slot data received from server on connection
        self.slot_data: dict = {}
        # Both mode: toggle between item/radar display
        self.hint_both_toggle: bool = False
        self.hint_both_last_toggle: float = 0.0
        # Detected game language (set during DAY_NUMBER == 0 phase)
        self.detected_language: str = "en"  # default English
        self._language_confirmed: bool = False

    def _save_key(self) -> str:
        slot_data = getattr(self, "slot_data", {}) or {}
        suffix = slot_data.get("game_id_suffix", "")
        if suffix:
            return f"applied_{self.auth}_P1P{suffix}"
        seed = getattr(self, "seed_name", None) or "unknown"
        return f"applied_{self.auth}_{seed}"

    def load_applied(self) -> None:
        key = self._save_key()
        if self.debug_hint:
            logger.info(f"[DEBUG] load_applied key: {key}")
        try:
            data = Utils.persistent_load().get("pikmin", {}).get(self._save_key(), {})
            self.pikmin_items_applied = {int(k): v for k, v in data.items()}
            if self.debug_hint:
                logger.info(f"[DEBUG] Loaded {len(self.pikmin_items_applied)} applied Pikmin items")
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

    def on_package(self, cmd: str, args: dict) -> None:
        if self.debug_hint:
            logger.info(f"[DEBUG] on_package cmd={cmd}")
        super().on_package(cmd, args)
        if cmd == "Connected":
            self.slot_data = args.get("slot_data", {})
            if not getattr(self, "seed_name", None):
                self.seed_name = args.get("seed_name", "unknown")
            if self.debug_hint:
                logger.info(f"[DEBUG] slot_data reçu: {self.slot_data}")
            self.pikmin_items_applied = {}  # reset before loading with correct key
            self.pikmin_dyn_pending = {"red": 0, "yellow": 0, "blue": 0}
            self.load_applied()
            self.needs_location_scout = True
            # Register for hints notifications
            self.stored_data_notification_keys.add(f"_read_hints_{self.team}_{self.slot}")
        elif cmd == "LocationInfo":
            count = len(args.get("locations", []))
            if self.debug_hint:
                logger.info(f"[DEBUG] Received LocationInfo with {count} locations")
            for item in args["locations"]:
                loc_id = item.location
                try:
                    item_name = self.item_names.lookup_in_slot(item.item, item.player)
                except Exception:
                    item_name = str(item.item)
                entry = {
                    "item_name": item_name,
                    "player":    item.player,
                    "flags":     item.flags if hasattr(item, "flags") else 0,
                }
                self.scouted_locations[loc_id] = entry
                self.all_locations_scouted[loc_id] = entry
            self.scout_received = True
            if self.debug_hint:
                logger.info(f"[DEBUG] Scouted {len(self.scouted_locations)} locations total")

        elif cmd == "SetReply":
            if args.get("key") == f"_read_hints_{self.team}_{self.slot}":
                hints = args.get("value", [])
                if self.debug_hint:
                    logger.info(f"[DEBUG] Received hints via SetReply: {len(hints)} hints")
                for hint in hints:
                    loc_id = hint.get("location")
                    if loc_id:
                        self.server_hints[loc_id] = hint
                if self.debug_hint:
                    logger.info(f"[DEBUG] Server hints total: {len(self.server_hints)}")

        elif cmd == "ReceivedHints":
            if self.debug_hint:
                logger.info(f"[DEBUG] ReceivedHints: {len(args.get('hints', []))} hints")
            for hint in args.get("hints", []):
                loc_id = hint.get("location")
                if loc_id:
                    self.server_hints[loc_id] = hint
            if self.debug_hint:
                logger.info(f"[DEBUG] Server hints total: {len(self.server_hints)}")


async def handle_pikmin_items(ctx: P1Context, game: Game) -> None:
    """Apply received Pikmin bonus items.

    Two writes per item:
    1. Stage persistent (0x803D6C7x) — survives day transitions, read by game at day start.
    2. Dynamic onion RAM (base_red + 0x10/14/18) — visible immediately in-game.
       base_red is found by scanning RAM at day-start (sentinel 0->nonzero) and matching
       the known persistent Leaf/Bud/Flower values at offsets +0x10/+0x14/+0x18.
       Yellow/Blue dynamic TBD — only Red enabled for now.
    """
    if game not in ONION_STAGE_ADDRS_CLIENT:
        return

    stage_addrs   = ONION_STAGE_ADDRS_CLIENT[game]
    sentinel_addr = ONION_DYN_SENTINEL.get(game)

    id_to_pikmin: dict[int, tuple[str, str, int]] = {
        FILLER_ITEMS[name]: PIKMIN_BONUS_ITEMS[name]
        for name in PIKMIN_BONUS_ITEMS
        if name in FILLER_ITEMS
    }

    def read_u32(addr: int) -> int:
        try:
            return int.from_bytes(dme.read_bytes(addr, 4), "big")
        except Exception:
            return 0

    def write_u32(addr: int, value: int) -> None:
        try:
            dme.write_bytes(addr, max(0, value).to_bytes(4, "big"))
        except Exception as e:
            logger.debug(f"Error writing u32 to 0x{addr:08x}: {e}")

    # Detect day-start: sentinel 0 -> nonzero.
    # 0x803D6D20 stays zero until the first day is loaded (even on title screen).
    day_start_detected = False
    if sentinel_addr is not None:
        sentinel_val = read_u32(sentinel_addr)
        sentinel_zero = (sentinel_val == 0)
        if ctx._onion_dyn_was_zero and not sentinel_zero:
            day_start_detected = True
            if ctx.debug_pbonus:
                logger.info(
                    f"[DEBUG] Day start detected (sentinel 0->0x{sentinel_val:08X})"
                )
        ctx._onion_dyn_was_zero = sentinel_zero

    # On day-start, scan RAM to find base_red dynamique.
    # Pattern: ram[addr+0x10]==leaf AND ram[addr+0x14]==bud AND ram[addr+0x18]==flower
    # with leaf/bud/flower read from stable persistent addresses.
    # Result cached in ctx._dyn_base_red until next day-start.
    if day_start_detected:
        ctx._dyn_base_red = None  # invalidate cache
        leaf  = read_u32(stage_addrs["red"]["leaf"])
        bud   = read_u32(stage_addrs["red"]["bud"])
        flower = read_u32(stage_addrs["red"]["flower"])

        if leaf > 0 or bud > 0 or flower > 0:
            scan_start = 0x81000000
            scan_end   = 0x81200000

            def _scan() -> int | None:
                try:
                    # Read the entire range in one call to minimise DME overhead
                    data = dme.read_bytes(scan_start, scan_end - scan_start)
                    for i in range(0, len(data) - 0x1C, 4):
                        if (int.from_bytes(data[i+0x10:i+0x14], "big") == leaf and
                            int.from_bytes(data[i+0x14:i+0x18], "big") == bud  and
                            int.from_bytes(data[i+0x18:i+0x1C], "big") == flower):
                            return scan_start + i
                except Exception as e:
                    logger.debug(f"[DEBUG] RAM scan error: {e}")
                return None

            loop = asyncio.get_event_loop()
            base = await loop.run_in_executor(None, _scan)
            if base is not None:
                ctx._dyn_base_red = base
                if ctx.debug_pbonus:
                    logger.info(f"[DEBUG] base_red found at 0x{base:08X}")
            else:
                if ctx.debug_pbonus:
                    logger.info(
                        f"[DEBUG] base_red NOT found (leaf={leaf} bud={bud} flower={flower})"
                    )

    # Dynamic offsets within base_red structure (confirmed in DME)
    DYN_RED_OFFSETS = {"leaf": 0x10, "bud": 0x14, "flower": 0x18}

    # In-game = sentinel nonzero AND DAY_NUMBER != 0
    try:
        current_day = dme.read_byte(DAY_NUMBER[game])
    except Exception:
        current_day = 0
    in_game = (not ctx._onion_dyn_was_zero) and (current_day != 0)

    def add_pikmin(color: str, stage: str, amount: int) -> None:
        # Always write to stage persistent (survives day transitions)
        s_addr = stage_addrs[color][stage]
        old_s = read_u32(s_addr)
        write_u32(s_addr, old_s + amount)
        if ctx.debug_pbonus:
            logger.info(
                f"[DEBUG] STAGE 0x{s_addr:08X} {color}/{stage} : {old_s} -> {old_s + amount} (+{amount})"
            )

        # Write to dynamic onion RAM when in-game (item received during the day).
        if in_game and color == "red":
            base = getattr(ctx, "_dyn_base_red", None)
            if base and stage in DYN_RED_OFFSETS:
                d_addr = base + DYN_RED_OFFSETS[stage]
                old_d = read_u32(d_addr)
                write_u32(d_addr, old_d + amount)
                if ctx.debug_pbonus:
                    logger.info(
                        f"[DEBUG] DYN   0x{d_addr:08X} red/{stage} : {old_d} -> {old_d + amount} (+{amount})"
                    )

    for item in ctx.items_received:
        item_id = item.item
        if item_id not in id_to_pikmin:
            continue

        color, stage, count = id_to_pikmin[item_id]
        total_received = sum(1 for i in ctx.items_received if i.item == item_id)
        already_applied = ctx.pikmin_items_applied.get(item_id, 0)
        to_apply = total_received - already_applied
        if to_apply <= 0:
            continue

        bonus = count * to_apply
        if ctx.debug_pbonus:
            logger.info(f"[DEBUG] Item  {color}/{stage} +{bonus} (item_id={item_id})")
        add_pikmin(color, stage, bonus)
        ctx.pikmin_items_applied[item_id] = total_received

    ctx.save_applied()


async def handle_parts(ctx: P1Context, game: Game):
    for name, data in ALL_PARTS.items():
        # check locations if something got collected
        read = dme.read_byte(data.memory_address[game])

        # freshly collected
        if read == data.collected_byte and data.ap_id not in ctx.checked_locations:
            ctx.locations_checked.add(data.ap_id)
            await ctx.check_locations([data.ap_id])


async def handle_pikmin_locations(ctx: P1Context, game: Game):
    """Handle Pikmin collection location checking"""
    try:
        if game not in PIKMIN_ADDRESSES:
            return

        addresses = PIKMIN_ADDRESSES[game]

        # Read current Pikmin counts
        red_count    = dme.read_byte(addresses["red"])
        yellow_count = dme.read_byte(addresses["yellow"])
        blue_count   = dme.read_byte(addresses["blue"])

        # Only act if counts have changed since last tick
        if (red_count == ctx.last_red_count
                and yellow_count == ctx.last_yellow_count
                and blue_count == ctx.last_blue_count):
            return

        ctx.last_red_count    = red_count
        ctx.last_yellow_count = yellow_count
        ctx.last_blue_count   = blue_count

        current_counts = {
            "red":    red_count,
            "yellow": yellow_count,
            "blue":   blue_count,
        }

        # Build reverse map once: ap_id -> (color, threshold)
        id_to_pikmin: dict[int, tuple[str, int]] = {}
        for loc_name, loc_id in PIKMIN_LOCATIONS_MAP.items():
            parts = loc_name.split(" Pikmin: ")
            if len(parts) == 2:
                id_to_pikmin[loc_id] = (parts[0].lower(), int(parts[1]))

        locations_to_check = []

        for loc_id in ctx.missing_locations:
            if loc_id not in id_to_pikmin:
                continue
            color, threshold = id_to_pikmin[loc_id]
            if current_counts[color] >= threshold:
                locations_to_check.append(loc_id)

        if locations_to_check:
            await ctx.check_locations(locations_to_check)

        ctx.pikmin_counts["red"]    = red_count
        ctx.pikmin_counts["yellow"] = yellow_count
        ctx.pikmin_counts["blue"]   = blue_count

    except Exception as e:
        logger.debug(f"Error handling Pikmin locations: {e}")


async def handle_areas(ctx: P1Context, game: Game):
    # Build set of valid ship part IDs for fast lookup
    ship_part_ids = {data.ap_id for data in ALL_PARTS.values()}

    # Count only real ship parts received
    ship_parts_count = sum(1 for item in ctx.items_received if item.item in ship_part_ids)

    total_required = 0

    if ship_parts_count >= 30:
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


async def handle_day_cycle(ctx: P1Context, game: Game) -> None:
    """Manage the day counter based on the player's day cycle option."""
    slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
    mode  = slot_data.get("day_cycle_mode",  0)  # 0=normal, 1=custom_range, 2=fixed
    d_min = slot_data.get("day_cycle_min",   2)
    d_max = slot_data.get("day_cycle_max",  29)
    fixed = slot_data.get("day_cycle_fixed",  2)

    try:
        day = dme.read_byte(DAY_NUMBER[game])
    except Exception:
        return

    if day == 0:
        return  # Player is on the main menu, not in-game yet

    if ctx.debug_days:
        import time as _time
        _now = _time.monotonic()
        if _now - ctx._last_day_debug_log >= 60.0:
            logger.info(f"[DEBUG] Day cycle: day={day} mode={mode}")
            ctx._last_day_debug_log = _now

    new_day = day

    if mode == 0:  # normal: force 2 if day is 1 or above 29
        if day == 1 or day > 29:
            new_day = 2

    elif mode == 1:  # custom range
        low  = max(2, min(d_min, d_max))
        high = max(low, d_max)
        if day < low:
            new_day = low
        elif day > high:
            new_day = low

    elif mode == 2:  # fixed — lock on fixed value
        new_day = max(2, min(fixed, 29))

    if new_day != day:
        try:
            dme.write_byte(DAY_NUMBER[game], new_day)
        except Exception:
            pass


def build_hint_bytes(ctx: P1Context, part_name: str, hint_mode: int) -> bytes:
    """Build the hint as raw bytes, using ESC (0x1B) as GC color code prefix."""
    loc_id = ALL_PARTS[part_name].ap_id

    if hint_mode == 1:  # item mode: show what this location contains
        info = ctx.scouted_locations.get(loc_id)
        if not info:
            return b""
        item_name = info["item_name"]
        player_id = info["player"]
        player_name = ctx.player_names.get(player_id, str(player_id))
        flags = info.get("flags", 0)

        if flags & 0b100:
            item_color = "ff0000ff"
        elif flags & 0b010:
            item_color = "00ffffff"
        elif flags & 0b001:
            item_color = "cc00ffff"
        else:
            item_color = "b4ffffff"

        text = (
            f"\x1BCC[ff0000ff]{part_name}\x1BCC[b4ffffff]\n"
            f"Contains: \x1BCC[{item_color}]{item_name}\x1BCC[b4ffffff]\n"
            f"For: \x1BCC[ff0000ff]{player_name}\x1BCC[b4ffffff]"
        )
        result = text.encode("ascii", errors="replace")
        if len(result) < SHIP_PART_TEXT_LENGTH:
            result += b"\x00" * (SHIP_PART_TEXT_LENGTH - len(result))
        return result

    elif hint_mode == 2:  # super radar mode
        slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
        hints = slot_data.get("hints", {})
        hint_data = hints.get(part_name)

        if ctx.debug_hint:
            logger.info(f"[DEBUG] Super Radar - part: {part_name}, hints count: {len(hints)}, hint_data: {hint_data}")

        if hint_data:
            item_name   = hint_data.get("Item", "Unknown")
            location    = hint_data.get("Location", "Unknown")
            send_player = hint_data.get("Send Player", "Unknown")
            hint_class  = hint_data.get("Class", "Other")

            if ctx.debug_hint:
                logger.info(f"[DEBUG] Super Radar - Item: {item_name}, Location: {location}, SendPlayer: {send_player}, Class: {hint_class}")

            if hint_class == "Prog":
                item_color = "cc00ffff"
            elif hint_class == "Trap":
                item_color = "ff0000ff"
            else:
                item_color = "00ffffff"

            text = (
                f"\x1BCC[ff0000ff]{part_name}\x1BCC[b4ffffff]\n"
                f"Your Ship Part is at \x1BCC[ff0000ff]{location}\x1BCC[b4ffffff] in \x1BCC[ff0000ff]{send_player}\x1BCC[b4ffffff]"
            )
        else:
            if ctx.debug_hint:
                logger.info(f"[DEBUG] Super Radar - No hint data found for {part_name}")
            text = (
                f"\x1BCC[cc00ff]{part_name}\x1BCC[b4ffffff]\n"
                f"\x1BCC[00ffffff]No hint data"
            )

        result = text.encode("ascii", errors="replace")
        if len(result) < SHIP_PART_TEXT_LENGTH:
            result += b"\x00" * (SHIP_PART_TEXT_LENGTH - len(result))
        return result

    elif hint_mode == 3:  # both mode: show item content AND super radar info
        slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
        hints = slot_data.get("hints", {})
        radar_hint_key = f"{part_name}_radar"

        info = ctx.scouted_locations.get(loc_id)
        radar_hint_data = hints.get(radar_hint_key)
        if not radar_hint_data:
            radar_hint_data = hints.get(part_name)

        if not info or not radar_hint_data:
            if ctx.debug_hint:
                logger.info(f"[DEBUG] Both - Missing data: info={bool(info)}, radar_hint_data={bool(radar_hint_data)}")
            return b""

        item_name   = info["item_name"]
        player_id   = info["player"]
        player_name = ctx.player_names.get(player_id, str(player_id))
        flags       = info.get("flags", 0)

        if flags & 0b100:
            item_color = "ff0000ff"
        elif flags & 0b010:
            item_color = "00ffffff"
        elif flags & 0b001:
            item_color = "cc00ffff"
        else:
            item_color = "b4ffffff"

        location    = radar_hint_data.get("Location", "Unknown")
        send_player = radar_hint_data.get("Send Player", "Unknown")

        text = (
            f"\x1BCC[ff0000ff]{part_name}\x1BCC[b4ffffff]\n"
            f"Contains: \x1BCC[{item_color}]{item_name}\x1BCC[b4ffffff]\n"
            f"For: \x1BCC[ff0000ff]{player_name}\x1BCC[b4ffffff]\n"
            f"\nYour Ship Part is at:\n\x1BCC[ff0000ff]{location}\x1BCC[b4ffffff]\n"
            f"in \x1BCC[ff0000ff]{send_player}\x1BCC[b4ffffff]"
        )
        if ctx.debug_hint:
            logger.info(f"[DEBUG] Both hint text length: {len(text)}")
        result = text.encode("ascii", errors="replace")
        if len(result) < SHIP_PART_TEXT_LENGTH:
            result += b"\x00" * (SHIP_PART_TEXT_LENGTH - len(result))
        return result

    return b""


async def handle_ship_part_hints(ctx: P1Context, game: Game) -> None:
    """Detect which ship part text is displayed and replace it with an Archipelago hint.
    Re-applies the hint every tick as long as the original game text is still visible,
    so the game cannot permanently overwrite our text."""
    # Only PAL supported for now (NTSC-U address TBD)
    if game != b"GPIP01":
        return

    slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
    hint_mode = slot_data.get("ship_part_hint_mode", 0)
    if hint_mode == 0:
        return

    hint_mode_is_both = hint_mode == 3

    try:
        raw = dme.read_bytes(SHIP_PART_TEXT_ADDR, SHIP_PART_TEXT_LENGTH)
    except Exception:
        return

    if not any(raw):
        ctx.last_hint_shown = ""
        ctx.last_hint_bytes = b""
        return

    first_newline = raw.find(b"\n")
    first_line = raw[:first_newline] if first_newline != -1 else raw
    detected_part = None
    lang = getattr(ctx, "detected_language", "en")

    for part_name in ALL_PARTS:
        if lang == "en":
            if part_name.encode("ascii") in first_line:
                detected_part = part_name
                break
        else:
            # Try the detected language first, fall back to English
            translated = SHIP_PART_TRANSLATIONS.get(part_name, {}).get(lang)
            if translated and translated in first_line:
                detected_part = part_name
                break
            if part_name.encode("ascii") in first_line:
                detected_part = part_name
                break

    if not detected_part:
        if ctx.last_hint_shown and ctx.last_hint_bytes:
            part_bytes = ctx.last_hint_shown.encode("ascii")
            if part_bytes in raw:
                if hint_mode_is_both:
                    elapsed = time.monotonic() - ctx.hint_both_last_toggle
                    if elapsed >= BOTH_MODE_TOGGLE_INTERVAL:
                        ctx.hint_both_toggle = not ctx.hint_both_toggle
                        ctx.hint_both_last_toggle = time.monotonic()
                        current_hint_mode = 1 if not ctx.hint_both_toggle else 2
                        new_hint_bytes = build_hint_bytes(ctx, ctx.last_hint_shown, current_hint_mode)
                        if new_hint_bytes:
                            ctx.last_hint_bytes = new_hint_bytes
                            if ctx.debug_hint:
                                logger.info(f"[DEBUG] Both mode toggle: mode={current_hint_mode}")
                            try:
                                dme.write_bytes(SHIP_PART_TEXT_ADDR, ctx.last_hint_bytes)
                            except Exception as e:
                                logger.debug(f"Error re-applying hint: {e}")
                else:
                    try:
                        dme.write_bytes(SHIP_PART_TEXT_ADDR, ctx.last_hint_bytes)
                    except Exception as e:
                        logger.debug(f"Error re-applying hint: {e}")
        return

    if detected_part != ctx.last_hint_shown:
        loc_id = ALL_PARTS[detected_part].ap_id
        ctx.hint_both_toggle = False
        ctx.hint_both_last_toggle = time.monotonic()

        if hint_mode == 1 or hint_mode_is_both:
            item_hint_key = f"{detected_part}_item" if hint_mode_is_both else detected_part
            if item_hint_key not in ctx.created_hints:
                ctx.created_hints.add(item_hint_key)
                await ctx.send_msgs([{
                    "cmd": "CreateHints",
                    "locations": [loc_id],
                    "player": ctx.slot,
                }])
                if ctx.debug_hint:
                    logger.info(f"[DEBUG] CreateHints sent for {detected_part} (loc_id={loc_id})")

        if hint_mode == 2 or hint_mode_is_both:
            slot_hints: dict = (ctx.slot_data or {}).get("hints", {})
            radar_hint_key = f"{detected_part}_radar" if hint_mode_is_both else detected_part
            hint_data = slot_hints.get(radar_hint_key)
            if not hint_data:
                hint_data = slot_hints.get(detected_part)
            if hint_data and radar_hint_key not in ctx.created_hints:
                ctx.created_hints.add(radar_hint_key)
                try:
                    target_loc_id = int(hint_data.get("Location ID", 0))
                    target_player = int(hint_data.get("Send Player ID", ctx.slot))
                except (ValueError, TypeError):
                    target_loc_id = 0
                    target_player = ctx.slot
                if target_loc_id:
                    await ctx.send_msgs([{
                        "cmd": "CreateHints",
                        "locations": [target_loc_id],
                        "player": target_player,
                    }])
                    if ctx.debug_hint:
                        logger.info(f"[DEBUG] Super Radar CreateHints for {detected_part} "
                                    f"(loc_id={target_loc_id}, player={target_player})")

        current_hint_mode = hint_mode
        hint_bytes = build_hint_bytes(ctx, detected_part, current_hint_mode)
        if not hint_bytes:
            if ctx.debug_hint:
                logger.info(f"[DEBUG] No hint text for {detected_part} (scouted={len(ctx.scouted_locations)})")
            return

        ctx.last_hint_shown = detected_part
        ctx.last_hint_bytes = hint_bytes

        if ctx.debug_hint:
            logger.info(f"[DEBUG] Writing hint for {detected_part} (mode={current_hint_mode})")

        try:
            dme.write_bytes(SHIP_PART_TEXT_ADDR, hint_bytes)
        except Exception as e:
            logger.debug(f"Error writing hint text: {e}")

    else:
        if ctx.last_hint_bytes:
            try:
                dme.write_bytes(SHIP_PART_TEXT_ADDR, ctx.last_hint_bytes)
            except Exception as e:
                logger.debug(f"Error re-applying hint: {e}")
        elif ctx.scouted_locations or ctx.all_locations_scouted:
            hint_bytes = build_hint_bytes(ctx, detected_part, hint_mode)
            if hint_bytes:
                ctx.last_hint_bytes = hint_bytes
                if ctx.debug_hint:
                    logger.info(f"[DEBUG] Late hint build for {detected_part}")
                try:
                    dme.write_bytes(SHIP_PART_TEXT_ADDR, hint_bytes)
                except Exception as e:
                    logger.debug(f"Error writing late hint: {e}")


async def dolphin_loop(ctx: P1Context):
    game_version = None

    while not ctx.exit_event.is_set():
        try:
            await asyncio.wait_for(ctx.watcher_event.wait(), 1.0)
        except asyncio.TimeoutError:
            pass

        ctx.watcher_event.clear()

        if ctx.needs_location_scout:
            ctx.needs_location_scout = False
            ctx.scout_sent = True
            ctx.scout_sent_time = time.monotonic()
            ctx.scout_received = False

            all_locations = list(ALL_LOCATIONS.values())

            slot_data = ctx.slot_data if hasattr(ctx, "slot_data") and ctx.slot_data else {}
            hint_mode_val = slot_data.get("ship_part_hint_mode", 0)
            if hint_mode_val == 2 or hint_mode_val == 3:
                all_server_locs = set(ctx.checked_locations) | set(ctx.missing_locations)
                all_locations = list(all_server_locs)
                logger.info(f"[Super Radar] Sending LocationScouts for {len(all_locations)} locations")

            logger.info(f"[DEBUG] Sending LocationScouts with {len(all_locations)} locations")
            await ctx.send_msgs([{
                "cmd": "LocationScouts",
                "locations": all_locations,
                "create_as_hint": 0,
            }])

        if ctx.scout_sent and not ctx.scout_received:
            elapsed = time.monotonic() - ctx.scout_sent_time
            if elapsed >= SCOUT_RETRY_INTERVAL:
                ctx.scout_sent_time = time.monotonic()
                logger.info(f"[DEBUG] Retrying LocationScouts (no response after {elapsed:.0f}s, "
                            f"scouted={len(ctx.scouted_locations)})")
                await ctx.send_msgs([{
                    "cmd": "LocationScouts",
                    "locations": list(ALL_LOCATIONS.values()),
                    "create_as_hint": 0,
                }])

        try:
            loop = asyncio.get_event_loop()

            # Run blocking DME calls in an executor with a timeout so that
            # closing Dolphin while the client is running does not freeze the process.
            def _dme_tick():
                if not dme.is_hooked():
                    dme.hook()
                if not dme.is_hooked():
                    return None
                return dme.read_bytes(0x80000000, 6)

            try:
                game = await asyncio.wait_for(
                    loop.run_in_executor(None, _dme_tick),
                    timeout=3.0
                )
            except asyncio.TimeoutError:
                logger.warning("[Pikmin] Dolphin read timed out — emulator may have closed.")
                ctx.dolphin_status_text = "Disconnected - Emulator closed"
                try:
                    dme.un_hook()
                except Exception:
                    pass
                game_version = None
                continue

            if game is None:
                ctx.dolphin_status_text = "Disconnected - Hook Failed"
                continue

            # Build expected patched Game ID from slot_data
            slot_data = getattr(ctx, "slot_data", {}) or {}
            suffix = slot_data.get("game_id_suffix", "")

            if not suffix:
                # Not yet connected to AP server — accept any P1P patched ISO
                if not game.startswith(b"P1P"):
                    ctx.dolphin_status_text = "Connected - Wrong Game (patch your ISO first)"
                    continue
                game_version = b"GPIP01"
            else:
                expected_patched_id = b"P1P" + suffix.encode("ascii")
                if game != expected_patched_id:
                    ctx.dolphin_status_text = f"Connected - Wrong Game (expected {expected_patched_id.decode()})"
                    continue
                game_version = b"GPIP01"

            ctx.dolphin_status_text = f"Connected - {game.decode()}"

            if game == b"GPIE01":
                _now = time.monotonic()
                if _now - ctx._last_ntsc_warning >= 60.0:
                    logger.warning(
                        "Warning : You use Pikmin NTSC This version does not completely support "
                        "the risk of bugs and crashes is very high"
                    )
                    ctx._last_ntsc_warning = _now
        except Exception as e:
            logger.error(e)
            logger.info("Trying to reconnect to Dolphin...")
            ctx.dolphin_status_text = "??? - Exception Occured"
            dme.un_hook()
            continue

        await handle_parts(ctx, game_version)
        await handle_pikmin_locations(ctx, game_version)
        await handle_pikmin_items(ctx, game_version)
        await handle_day_cycle(ctx, game_version)
        await handle_ship_part_hints(ctx, game_version)
        await handle_areas(ctx, game_version)
        # TODO if "DeathLink" in ctx.tags: handle that

        # Language detection — only while DAY_NUMBER == 0 (main menu).
        # Once DAY_NUMBER != 0 the player is in-game and language cannot change.
        try:
            day_number = struct.unpack(">B", dme.read_bytes(0x803A2937, 1))[0]
            if day_number == 0:
                # Still on main menu — keep checking every tick
                ctx._language_confirmed = False
                for addr_a, addr_b, lang_bytes, lang_code in LANGUAGE_DETECT_TABLE:
                    try:
                        val_a = dme.read_bytes(addr_a, len(lang_bytes))
                        val_b = dme.read_bytes(addr_b, len(lang_bytes))
                        if val_a == lang_bytes and val_b == lang_bytes:
                            if ctx.detected_language != lang_code:
                                msg = LANG_MSG_DETECTED.get(lang_code, LANG_MSG_DETECTED["en"])
                                logger.info(f"[Pikmin] {msg} : {LANG_NAMES.get(lang_code, lang_code)}")
                                ctx.detected_language = lang_code
                            break
                    except Exception:
                        pass
            elif not ctx._language_confirmed:
                # Player just entered the game — lock the language
                lc = ctx.detected_language
                msg = LANG_MSG_LOCKED.get(lc, LANG_MSG_LOCKED["en"])
                logger.info(f"[Pikmin] {msg} : {LANG_NAMES.get(lc, lc)}")
                ctx._language_confirmed = True
        except Exception:
            pass


def run_client(*args) -> None:
    # args may contain the path to a .appik1 file when launched via double-click
    appik1_path = args[0] if args and isinstance(args[0], str) and args[0].endswith(".appik1") else None

    async def main() -> None:
        parser = get_base_parser()
        parser.add_argument("appik1_file", default="", type=str, nargs="?",
                            help="Path to a .appik1 patch file")
        parsed = parser.parse_args()

        # Resolve patch path from args or CLI argument
        patch_path = appik1_path
        if not patch_path and parsed.appik1_file:
            patch_path = parsed.appik1_file

        # Patch the ISO in a thread executor (avoids blocking the event loop and
        # prevents a stray console window from appearing on Windows)
        if patch_path and os.path.isfile(patch_path):
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _handle_patch, patch_path)

        ctx = P1Context(parsed.connect, parsed.password)
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


def _handle_patch(appik1_path: str) -> None:
    """Patch a copy of the user's Pikmin 1 PAL ISO when a .appik1 file is opened.

    The ISO path must be configured in host.yml under pikmin_options.iso_file.
    No external window or dialog is opened — everything goes through the AP logger
    and Utils.messagebox (which is safe to call from any thread).
    """
    from .P1Rom import verify_iso, patch_iso, InvalidISOError
    from settings import get_settings
    import shutil

    options = get_settings()
    iso_path = options.get("pikmin_options", {}).get("iso_file", "")
    if iso_path and not os.path.isfile(iso_path):
        iso_path = Utils.user_path(iso_path)

    if not iso_path or not os.path.isfile(iso_path):
        msg = (
            "No valid Pikmin 1 PAL ISO found.\n\n"
            "Please set the ISO path in host.yml:\n"
            "  pikmin_options:\n"
            "    iso_file: C:/path/to/Pikmin1.iso"
        )
        logger.error(f"[Pikmin] {msg}")
        Utils.messagebox("Cannot Patch Pikmin 1", msg, error=True)
        return

    # Build output path: same folder as the .appik1, same name as ISO
    patch_dir = os.path.dirname(os.path.abspath(appik1_path))
    patch_basename = os.path.splitext(os.path.basename(appik1_path))[0]
    iso_ext = os.path.splitext(iso_path)[1]
    output_iso = os.path.join(patch_dir, patch_basename + iso_ext)

    # Copy the clean ISO to the output path
    try:
        shutil.copy2(iso_path, output_iso)
        logger.info(f"[Pikmin] Copied clean ISO to: {output_iso}")
    except Exception as e:
        Utils.messagebox("Cannot Patch Pikmin 1", f"Could not copy ISO:\n{e}", error=True)
        return

    # Read seed from .appik1
    seed = ""
    try:
        import zipfile, json
        with zipfile.ZipFile(appik1_path, "r") as zf:
            with zf.open("patch.appik1") as f:
                data = json.load(f)
                seed = str(data.get("Seed", ""))
    except Exception as e:
        logger.warning(f"[Pikmin] Could not read seed from .appik1: {e}")

    # Verify and patch the copy
    try:
        verify_iso(output_iso)
        patch_iso(output_iso, seed=seed)
        logger.info(f"[Pikmin] ISO patched successfully: {output_iso}")
        Utils.messagebox(
            "Pikmin 1 Patched",
            f"Patched ISO created successfully!\n{output_iso}"
        )
    except InvalidISOError as e:
        logger.error(f"[Pikmin] ISO verification failed: {e}")
        try:
            os.remove(output_iso)
        except Exception:
            pass
        Utils.messagebox("Cannot Patch Pikmin 1", str(e), error=True)
    except Exception as e:
        logger.error(f"[Pikmin] Unexpected error during patching: {e}")
        try:
            os.remove(output_iso)
        except Exception:
            pass
        Utils.messagebox("Cannot Patch Pikmin 1", f"Unexpected error:\n{e}", error=True)


if __name__ == "__main__":
    run_client()