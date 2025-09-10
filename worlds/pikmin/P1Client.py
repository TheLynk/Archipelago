import asyncio
from typing import TYPE_CHECKING, Optional

import dolphin_memory_engine as dme

import Utils
from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus
from .P1UI import P1UI
from .P1Data import *

if TYPE_CHECKING:
    import kvui

UNLOCKED_AREAS: MemoryAddress = mem(0x803A2803, 0x8039D983)  # byte

COUNT_TOTAL_PARTS: MemoryAddress = mem(0x812427FF, 0x81249DE7)  # byte
COUNT_REQUIRED_PARTS: MemoryAddress = mem(0x81242803, 0x81249DEB)  # byte

# COUNT_LOCAL_PARTS_1: MemoryAddress = mem(0x81242807, 0x81249DEF)  # byte
# COUNT_LOCAL_PARTS_2: MemoryAddress = mem(0x81242808, 0x81249DF0)  # byte
# COUNT_LOCAL_PARTS_3: MemoryAddress = mem(0x81242809, 0x81249DF1)  # byte
# COUNT_LOCAL_PARTS_4: MemoryAddress = mem(0x8124280A, 0x81249DF2)  # byte
# COUNT_LOCAL_PARTS_5: MemoryAddress = mem(0x8124280B, 0x81249DF3)  # byte
#
# TIME_HOURS: MemoryAddress = mem(0x803A2930)  # word, daytime is 7-18, day ends >= 19, night mode (moon icon) <= 6
# TIME_MINUTES: MemoryAddress = mem(0x803A2924)  # word, explore how exactly this works


class P1CommandProcessor(ClientCommandProcessor):
    def __init__(self, ctx: CommonContext):
        super().__init__(ctx)


class P1Context(CommonContext):
    command_processor = P1CommandProcessor
    game: str = "Pikmin"
    items_handling: int = 0b111

    def __init__(self, server_address: Optional[str], password: Optional[str]) -> None:
        super().__init__(server_address, password)
        self.dolphin_status_text = "Disconnected"

    def make_gui(self) -> "type[kvui.GameManager]":
        return P1UI

    async def server_auth(self, password_requested: bool = False) -> None:
        if not self.auth:
            await self.get_username()

        await super().server_auth(password_requested)

        await self.send_connect()


async def handle_parts(ctx: P1Context, game: Game):
    for name, data in ALL_PARTS.items():
        # check locations if something got collected
        read = dme.read_byte(data.memory_address[game])

        # freshly collected
        if read == data.collected_byte and data.ap_id not in ctx.checked_locations:
            ctx.locations_checked.add(data.ap_id)
            await ctx.check_locations([data.ap_id])

    # if ctx.locations_checked == ctx.checked_locations:
    # client and server data match -> it's safe to change memory
    # here we could do the following:
    # - put parts whose location we have checked but whose item we haven't received yet to 0 (should be safe)
    # - put parts whose item we have received but whose location we haven't checked yet to 3
    # the latter could be prone to TOCTOU errors where we read and check it at 0, then it gets collected ingame
    # and becomes 1/2, then we set it to 3, never noticing that it got collected (it can't ever get collected again)
    # currently doing neither so that parts on the ship == locations checked instead of items received or sth mixed
    # consider only updating the latter case (or both) in menus/paused once we can detect that

async def handle_areas(ctx: P1Context, game: Game):
    total = len(ctx.items_received)
    total_required = 0

    if total >= 30:  # lazy: this makes olimar succeed once all parts have been collected
        total_required = 25

        if not ctx.finished_game:
            await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            # TODO is sending this msg guaranteed to succeed?
            ctx.finished_game = True

    areas = 0b00001
    if total >= 1:
        areas += 0b00010
    if total >= 5:
        areas += 0b00100
    if total >= 12:
        areas += 0b01000
    if total >= 29:
        areas += 0b10000

    dme.write_byte(COUNT_TOTAL_PARTS[game], total)
    dme.write_byte(COUNT_REQUIRED_PARTS[game], total_required)
    dme.write_byte(UNLOCKED_AREAS[game], areas)


async def dolphin_loop(ctx: P1Context):
    game_version = None

    while not ctx.exit_event.is_set():
        try:
            await asyncio.wait_for(ctx.watcher_event.wait(), 1.0)
        except asyncio.TimeoutError:
            pass

        ctx.watcher_event.clear()

        try:
            # could maybe just do the else branch and check for game there
            if not dme.is_hooked():
                dme.hook()  # silently fails?
            if not dme.is_hooked():
                ctx.dolphin_status_text = "Disconnected - Hook Failed"
                continue
            else:
                game = dme.read_bytes(0x80000000, 6)
                if game not in [b"GPIP01", b"GPIE01"]:
                    ctx.dolphin_status_text = "Connected - Wrong Game"
                    continue

                game_version = game
                ctx.dolphin_status_text = f"Connected - {game.decode()}"
                # TODO preferably check that the game is in a save file too
        except Exception as e:
            logger.error(e)
            logger.info("Trying to reconnect to Dolphin...")
            ctx.dolphin_status_text = "??? - Exception Occured"
            dme.un_hook()
            continue

        await handle_parts(ctx, game_version)
        await handle_areas(ctx, game_version)
        # TODO if "DeathLink" in ctx.tags: handle that


def run_client() -> None:
    async def main() -> None:
        parser = get_base_parser()
        args = parser.parse_args()

        ctx = P1Context(args.connect, args.password)
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


if __name__ == "__main__":
    run_client()
