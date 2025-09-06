from dataclasses import dataclass

from Options import DefaultOnToggle, PerGameCommonOptions


class FirstPartIsLocal(DefaultOnToggle):
    """
    Force collecting the Main Engine to give a ship part.
    This can be useful to prevent getting stuck immediately at the start of the game.
    """

    display_name = "Local First Part"


class LastPartIsLocal(DefaultOnToggle):
    """
    Force collecting the Secret Safe to give a ship part.
    Since you complete Pikmin 1 by collecting the last ship part, it could be give a required item for another player.
    This option prevents this, so other players won't ever need to wait for Pikmin to finish.
    """

    display_name = "Local Last Part"


@dataclass
class P1Options(PerGameCommonOptions):
    first_part_is_local: FirstPartIsLocal
    last_part_is_local: LastPartIsLocal
