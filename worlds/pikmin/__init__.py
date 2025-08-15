import os
import zipfile
from base64 import b64encode
from collections.abc import Mapping
from typing import Any, ClassVar

import yaml

from BaseClasses import Item
from BaseClasses import ItemClassification as IC
from BaseClasses import MultiWorld, Region, Tutorial
from Options import Toggle
from worlds.AutoWorld import WebWorld, World
from worlds.Files import APPlayerContainer
from worlds.generic.Rules import add_item_rule
from worlds.LauncherComponents import Component, SuffixIdentifier, Type, components, icon_paths, launch_subprocess

VERSION: tuple[int, int, int] = (3, 0, 0)

def run_client() -> None:
    """
    Launch the Pikmin client.
    """
    print("Running pikmin Client")
    from .PikminClient import main

    launch_subprocess(main, name="PikminClient")

components.append(
    Component(
        "Pikmin Client",
        func=run_client,
        component_type=Type.CLIENT,
        file_identifier=SuffixIdentifier(".appikmin"),
        icon="Pikmin",
    )
)
icon_paths["Pikmin"] = "ap:worlds.tww/assets/icon.png"

class PikminContainer(APPlayerContainer):
    """
    This class defines the container file for Pikmin
    """

    game: str = "Pikmin"
    patch_file_ending: str = ".appikmin"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if "data" in kwargs:
            self.data = kwargs["data"]
            del kwargs["data"]

        super().__init__(*args, **kwargs)

    def write_contents(self, opened_zipfile: zipfile.ZipFile) -> None:
        """
        Write the contents of the container file.
        """
        super().write_contents(opened_zipfile)

        # Record the data for the game under the key `plando`.
        opened_zipfile.writestr("plando", b64encode(bytes(yaml.safe_dump(self.data, sort_keys=False), "utf-8")))

class TWWWeb(WebWorld):
    """
    This class handles the web interface for Pikmin.

    The web interface includes the setup guide and the options page for generating YAMLs.
    """

    tutorials = [
        Tutorial(
            "Multiworld Setup Guide",
            "A guide to setting up the Archipelago The Wind Waker software on your computer.",
            "English",
            "setup_en.md",
            "setup/en",
            ["TheLynk"],
        ),
        Tutorial(
            "Multiworld Setup Guide",
            "A guide to setting up the Archipelago The Wind Waker software on your computer.",
            "Français",
            "setup_fr.md",
            "setup/fr",
            ["TheLynk"]
        )
    ]
    theme = "jungle"
    """options_presets = tww_options_presets
    option_groups = tww_option_groups"""
    rich_text_options_doc = True