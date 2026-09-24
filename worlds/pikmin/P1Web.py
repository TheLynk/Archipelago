from BaseClasses import Tutorial
from worlds.AutoWorld import WebWorld
from .P1Options import P1_OPTION_GROUPS


class P1Web(WebWorld):
    tutorials = [
        Tutorial(
            "Multiworld Setup Guide",
            "A guide to setting up the Archipelago Pikmin software on your computer.",
            "English",
            "setup_en.md",
            "setup/en",
            [""],
        )
    ]
    theme = "jungle"
    # options_presets = ...
    option_groups = P1_OPTION_GROUPS
    rich_text_options_doc = True
