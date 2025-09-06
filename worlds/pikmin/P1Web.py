from BaseClasses import Tutorial
from worlds.AutoWorld import WebWorld


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
    # option_groups = ...
    rich_text_options_doc = True
