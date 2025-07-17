import typing
from BaseClasses import Region, Entrance, Item, ItemClassification, Tutorial
from .Items import PikminItem, item_table, filler_item_name
from .Locations import PikminLocation, location_table
from .Options import Pikmin1Options
from .Rules import set_rules
from worlds.AutoWorld import World, WebWorld


class Pikmin1Web(WebWorld):
    theme = "grass"
    
    tutorials = [
        Tutorial(
            "Multiworld Setup Tutorial",
            "A guide to setting up Pikmin 1 for Archipelago multiworld.",
            "English",
            "setup_en.md",
            "setup/en",
            ["YourName"]
        )
    ]


class Pikmin1World(World):
    """
    Pikmin 1 is a real-time strategy game where Captain Olimar must collect ship parts
    with the help of plant-like creatures called Pikmin to repair his ship and escape
    the planet before his life support runs out.
    """
    
    game = "Pikmin 1"
    options_dataclass = Pikmin1Options
    options: Pikmin1Options
    topology_present = True
    web = Pikmin1Web()
    
    item_name_to_id = {name: data.code for name, data in item_table.items()}
    location_name_to_id = {name: data.code for name, data in location_table.items()}
    
    def __init__(self, world, player: int):
        super().__init__(world, player)
        
    def create_regions(self) -> None:
        """Create regions for the world."""
        menu_region = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu_region)
        
        # Create main game region
        main_region = Region("The Forest of Hope", self.player, self.multiworld)
        self.multiworld.regions.append(main_region)
        
        # Add locations to the main region
        main_region.locations += [
            PikminLocation(self.player, loc_name, loc_data.code, main_region)
            for loc_name, loc_data in location_table.items()
        ]
        
        # Connect regions
        menu_region.connect(main_region)
        
    def create_items(self) -> None:
        """Create items for the world."""
        # Create progression items
        itempool = []
        
        # Add ship parts as progression items
        for name, data in item_table.items():
            if data.progression:
                itempool.append(self.create_item(name))
        
        # Fill remaining slots with filler items
        filler_needed = len(location_table) - len(itempool)
        for _ in range(filler_needed):
            itempool.append(self.create_item(filler_item_name))
        
        self.multiworld.itempool += itempool
        
    def create_item(self, name: str) -> PikminItem:
        """Create an item by name."""
        data = item_table[name]
        return PikminItem(name, data.classification, data.code, self.player)
        
    def set_rules(self) -> None:
        """Set rules for the world."""
        set_rules(self)
        
    def fill_slot_data(self) -> typing.Dict[str, typing.Any]:
        """Fill slot data for the client."""
        return {
            "world_seed": self.multiworld.seed,
            "seed_name": self.multiworld.seed_name,
            "player_name": self.multiworld.get_player_name(self.player),
            "player_id": self.player,
        }
