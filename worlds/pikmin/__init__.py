# pyright: reportMissingImports=false
import os
import zipfile
from base64 import b64encode
from collections.abc import Mapping
from typing import Any, ClassVar
import logging

import yaml

from BaseClasses import Item
from BaseClasses import ItemClassification as IC
from BaseClasses import MultiWorld, Region, Tutorial
from Options import Toggle
from worlds.AutoWorld import WebWorld, World
from worlds.Files import APPlayerContainer
from worlds.generic.Rules import add_item_rule
from worlds.LauncherComponents import Component, SuffixIdentifier, Type, components, icon_paths, launch_subprocess

from .Items import PikminItem, ITEM_TABLE, PikminItemData, item_factory
from .Locations import LOCATION_TABLE, PikminLocation, PikminFlag
from .Options import PikminOptions
from .ItemPool import generate_itempool
from .Rules import set_rules

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
        description=("Launch Pikmin.\nAnd leaves to save the Captain Olimar.")
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
    Save Olimar
    """

    options_dataclass = PikminOptions
    options: PikminOptions

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

    origin_region_name: str = "The Crash Site"

    create_items = generate_itempool

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.progress_locations: set[str] = set()
        self.nonprogress_locations: set[str] = set()

        self.item_classification_overrides: dict[str, IC] = {}

        self.useful_pool: list[str] = []
        self.filler_pool: list[str] = []

    @staticmethod
    def _get_classification_name(classification: IC) -> str:
        """
        Return a string representation of the item's highest-order classification.

        :param classification: The item's classification.
        :return: A string representation of the item's highest classification. The order of classification is
        progression > trap > useful > filler.
        """

        if IC.progression in classification:
            return "progression"
        elif IC.trap in classification:
            return "trap"
        elif IC.useful in classification:
            return "useful"
        else:
            return "filler"
    
    def _determine_progress_and_nonprogress_locations(self) -> tuple[set[str], set[str]]:
        """
        Determine which locations are progress and nonprogress in the world based on the player's options.

        :return: A tuple of two sets, the first containing the names of the progress locations and the second containing
        the names of the nonprogress locations.
        """

        def add_flag(option: Toggle, flag: PikminFlag) -> PikminFlag:
            return flag if option else PikminFlag.ALWAYS

        options = self.options

        enabled_flags = PikminFlag.ALWAYS

        progress_locations: set[str] = set()
        nonprogress_locations: set[str] = set()
        for location, data in LOCATION_TABLE.items():
            if data.flags & enabled_flags == data.flags:
                progress_locations.add(location)
            else:
                nonprogress_locations.add(location)
        assert progress_locations.isdisjoint(nonprogress_locations)

        return progress_locations, nonprogress_locations

    def generate_early(self) -> None:
        """
        Run before any general steps of the MultiWorld other than options.
        """
        options = self.options

        # Determine which locations are progression and which are not from options.
        self.progress_locations, self.nonprogress_locations = self._determine_progress_and_nonprogress_locations()

        """# Determine any item classification overrides based on user options.
        self._determine_item_classification_overrides()"""

    def create_regions(self) -> None:
        """
        Create and connect regions for the Pikmin world.
        """
        multiworld = self.multiworld
        player = self.player

        regions: dict[str, Region] = {}

        # Crée chaque région si elle n’existe pas encore
        for name, data in LOCATION_TABLE.items():
            if data.region not in regions:
                region = Region(data.region, player, multiworld)
                multiworld.regions.append(region)
                regions[data.region] = region

            # Ajoute la location à la région correspondante
            location = PikminLocation(player, name, regions[data.region], data)
            regions[data.region].locations.append(location)
    
    def set_rules(self) -> None:
        """
        Set access and item rules on locations.
        """
        # Set the access rules for all progression locations.
        set_rules(self)

    def generate_output(self, output_directory: str) -> None:
        """
        Create the output APPIKMIN file that is used to randomize the ISO.

        :param output_directory: The output directory for the APPIKMIN file.
        """
        multiworld = self.multiworld
        player = self.player

                # Output seed name and slot number to seed RNG in randomizer client.
        output_data = {
            "Version": list(VERSION),
            "Seed": multiworld.seed_name,
            "Slot": player,
            "Name": self.player_name,
            "Locations": {},
        }

        # Output which item has been placed at each location.
        output_locations = output_data["Locations"]
        locations = multiworld.get_locations(player)
        for location in locations:
            if location.name != "Land to the Space":
                if location.item:
                    item_info = {
                        "player": location.item.player,
                        "name": location.item.name,
                        "game": location.item.game,
                        "classification": self._get_classification_name(location.item.classification),
                    }
                else:
                    item_info = {"name": "Nothing", "game": "Pikmin", "classification": "filler"}
                output_locations[location.name] = item_info

        # Output the plando details to file.
        appikmin = PikminContainer(
            path=os.path.join(
                output_directory, f"{multiworld.get_out_file_name_base(player)}{PikminContainer.patch_file_ending}"
            ),
            player=player,
            player_name=self.player_name,
            data=output_data,
        )
        appikmin.write()       
    
    def create_item(self, name: str) -> PikminItem:
        """
        Create an item for this world type and player.

        :param name: The name of the item to create.
        :raises KeyError: If an invalid item name is provided.
        """
        if name in ITEM_TABLE:
            return PikminItem(name, self.player, ITEM_TABLE[name], self.item_classification_overrides.get(name))
        raise KeyError(f"Invalid item name: {name}")
    
    def get_filler_item_name(self, strict: bool = True) -> str:
        """
        This method is called when the item pool needs to be filled with additional items to match the location count.

        :param strict: Whether the item should be one strictly classified as filler. Defaults to `True`.
        :return: The name of a filler item from this world.
        """
        # If there are still useful items to place, place those first.
        if not strict and len(self.useful_pool) > 0:
            return self.useful_pool.pop()

        # If there are still vanilla filler items to place, place those first.
        if len(self.filler_pool) > 0:
            return self.filler_pool.pop()

        # Use the same weights for filler items used in the base randomizer.
        filler_consumables = ["Nectar"]
        filler_weights = [1]
        """if not strict:
            filler_consumables.append("Carrot Pikpik")
            filler_weights.append(15)"""

        return self.multiworld.random.choices(filler_consumables, weights=filler_weights, k=1)[0]
        
    
    def fill_slot_data(self) -> Mapping[str, Any]:
        """
        Return the `slot_data` field that will be in the `Connected` network package.

        This is a way the generator can give custom data to the client.
        The client will receive this as JSON in the `Connected` response.

        :return: A dictionary to be sent to the client when it connects to the server.
        """
        slot_data = self.options.get_slot_data_dict()

        return slot_data
