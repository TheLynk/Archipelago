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

from .Items import PikminItem, ITEM_TABLE
from .Locations import LOCATION_TABLE, PikminLocation

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
icon_paths["Pikmin"] = "ap:worlds.pikmin/assets/icon.png"

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

class PikminWeb(WebWorld):
    """
    This class handles the web interface for Pikmin.

    The web interface includes the setup guide and the options page for generating YAMLs.
    """

    tutorials = [
        Tutorial(
            "Multiworld Setup Guide",
            "A guide to setting up the Archipelago Pikmin software on your computer.",
            "English",
            "setup_en.md",
            "setup/en",
            ["TheLynk"],
        ),
        Tutorial(
            "Multiworld Setup Guide",
            "A guide to setting up the Archipelago Pikmin software on your computer.",
            "Français",
            "setup_fr.md",
            "setup/fr",
            ["TheLynk"]
        )
    ]
    theme = "jungle"
    """options_presets = pikmin_options_presets
    option_groups = pikmin_option_groups"""
    rich_text_options_doc = True

class PikminWorld(World):
    """
    Blabla
    """

    """options_dataclass = PikminOptions
    options: PikminOptions"""

    game: ClassVar[str] = "Pikmin"
    topology_present: bool = True

    item_name_to_id: ClassVar[dict[str, int]] = {
        name: PikminItem.get_apid(data.code) for name, data in ITEM_TABLE.items() if data.code is not None
    }
    
    location_name_to_id: ClassVar[dict[str, int]] = {
        name: PikminLocation.get_apid(data.code) for name, data in LOCATION_TABLE.items() if data.code is not None
    }
    """
    item_name_groups: ClassVar[dict[str, set[str]]] = item_name_groups"""

    required_client_version: tuple[int, int, int] = (0, 5, 1)

    web: ClassVar[PikminWeb] = PikminWeb()

    origin_region_name: str = "Crash Site"

    """create_items = generate_itempool"""