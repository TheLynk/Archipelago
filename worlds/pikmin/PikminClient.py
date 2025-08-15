import asyncio
import time
import traceback
import logging
from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus
import dolphin_memory_engine
from typing import TYPE_CHECKING, Any, Optional
import Utils


if TYPE_CHECKING:
    import kvui

CONNECTION_REFUSED_GAME_STATUS = (
    "Dolphin failed to connect. Please load a randomized ROM for The Wind Waker. Trying again in 5 seconds..."
)
CONNECTION_REFUSED_SAVE_STATUS = (
    "Dolphin failed to connect. Please load into the save file. Trying again in 5 seconds..."
)
CONNECTION_LOST_STATUS = (
    "Dolphin connection was lost. Please restart your emulator and make sure The Wind Waker is running."
)
CONNECTION_CONNECTED_STATUS = "Dolphin connected successfully."
CONNECTION_INITIAL_STATUS = "Dolphin connection has not been initiated."

# Adresse mémoire des Pikmin rouges (PAL)
RED_PIKMIN_ADDRESS = 0x803D6CF7

class PikminContext(CommonContext):
    game = "Pikmin"
    items_handling = 0b000  # On ne gère pas encore les locations

    async def game_watcher(self):
        """Boucle qui lit le nombre de Pikmin rouges et l'affiche toutes les secondes."""
        while not self.exit_event.is_set():
            try:
                # Hooker Dolphin si ce n'est pas déjà fait
                if not dme.is_hooked():
                    dme.hook()

                if dme.is_hooked():
                    red_count = dme.read_u8(RED_PIKMIN_ADDRESS)
                    print(f"Pikmin rouges actuellement : {red_count}")
            except Exception as e:
                print(f"Erreur lecture RAM : {e}")

            await asyncio.sleep(1)  # toutes les secondes

def __init__(self, server_address: Optional[str], password: Optional[str]) -> None:
        """
        Initialize the TWW context.

        :param server_address: Address of the Archipelago server.
        :param password: Password for server authentication.
        """

        super().__init__(server_address, password)

async def disconnect(self, allow_autoreconnect: bool = False) -> None:
    """
    Disconnect the client from the server and reset game state variables.
    :param allow_autoreconnect: Allow the client to auto-reconnect to the server. Defaults to `False`.
    """
    self.auth = None
    self.salvage_locations_map = {}
    self.current_stage_name = ""
    self.visited_stage_names = None
    await super().disconnect(allow_autoreconnect)

async def server_auth(self, password_requested: bool = False) -> None:
    """
    Authenticate with the Archipelago server.

    :param password_requested: Whether the server requires a password. Defaults to `False`.
    """
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
    """
    Initialize the GUI for The Wind Waker client.
    :return: The client's GUI.
    """
    ui = super().make_gui()
    ui.base_title = "Archipelago The Wind Waker Client"
    return ui

async def dolphin_sync_task(ctx: PikminContext) -> None:
    """
    The task loop for managing the connection to Dolphin.

    While connected, read the emulator's memory to look for any relevant changes made by the player in the game.

    :param ctx: The Wind Waker client context.
    """
    logger.info("Starting Dolphin connector. Use /dolphin for status information.")
    sleep_time = 0.0
    while not ctx.exit_event.is_set():
        if sleep_time > 0.0:
            try:
                # ctx.watcher_event gets set when receiving ReceivedItems or LocationInfo, or when shutting down.
                await asyncio.wait_for(ctx.watcher_event.wait(), sleep_time)
            except asyncio.TimeoutError:
                pass
            sleep_time = 0.0
        ctx.watcher_event.clear()

        try:
            if dolphin_memory_engine.is_hooked() and ctx.dolphin_status == CONNECTION_CONNECTED_STATUS:
                sleep_time = 0.1
            else:
                if ctx.dolphin_status == CONNECTION_CONNECTED_STATUS:
                    logger.info("Connection to Dolphin lost, reconnecting...")
                    ctx.dolphin_status = CONNECTION_LOST_STATUS
                logger.info("Attempting to connect to Dolphin...")
                dolphin_memory_engine.hook()
                if dolphin_memory_engine.is_hooked():
                    if dolphin_memory_engine.read_bytes(0x80000000, 6) != b"GZLE99":
                        logger.info(CONNECTION_REFUSED_GAME_STATUS)
                        ctx.dolphin_status = CONNECTION_REFUSED_GAME_STATUS
                        dolphin_memory_engine.un_hook()
                        sleep_time = 5
                    else:
                        logger.info(CONNECTION_CONNECTED_STATUS)
                        ctx.dolphin_status = CONNECTION_CONNECTED_STATUS
                        ctx.locations_checked = set()
                else:
                    logger.info("Connection to Dolphin failed, attempting again in 5 seconds...")
                    ctx.dolphin_status = CONNECTION_LOST_STATUS
                    await ctx.disconnect()
                    sleep_time = 5
                    continue
        except Exception:
            dolphin_memory_engine.un_hook()
            logger.info("Connection to Dolphin failed, attempting again in 5 seconds...")
            logger.error(traceback.format_exc())
            ctx.dolphin_status = CONNECTION_LOST_STATUS
            await ctx.disconnect()
            sleep_time = 5
            continue

def main(connect: Optional[str] = None, password: Optional[str] = None) -> None:
    """
    Run the main async loop for Pikmin client.

    :param connect: Address of the Archipelago server.
    :param password: Password for server authentication.
    """
    Utils.init_logging("Pikmin Client")

    async def _main(connect: Optional[str], password: Optional[str]) -> None:
        ctx = PikminContext(connect, password)
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="ServerLoop")
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        await asyncio.sleep(1)

        ctx.dolphin_sync_task = asyncio.create_task(dolphin_sync_task(ctx), name="DolphinSync")

        await ctx.exit_event.wait()
        # Wake the sync task, if it is currently sleeping, so it can start shutting down when it sees that the
        # exit_event is set.
        ctx.watcher_event.set()
        ctx.server_address = None

        await ctx.shutdown()

        if ctx.dolphin_sync_task:
            await ctx.dolphin_sync_task

if __name__ == "__main__":
    parser = get_base_parser()
    args = parser.parse_args()
    main(args.connect, args.password)
