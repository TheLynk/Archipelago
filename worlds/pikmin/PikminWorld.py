import typing

from BaseClasses import Region, Entrance, Location, Item, Tutorial, ItemClassification
from worlds.AutoWorld import World, WebWorld
from .Items import item_table, PikminItem, item_name_to_id, get_progression_items
from .Locations import location_table, PikminLocation, location_name_to_id, Areas
from .Rules import set_rules
from .Options import PikminOptions

class PikminWeb(WebWorld):
    tutorials = [Tutorial(
        "Pikmin Setup Guide",
        "A guide to setting up the Pikmin randomizer.",
        "English",
        "setup_en.md",
        "setup/en",
        ["Pikmin"]
    )]

class PikminWorld(World):
    """
    Pikmin is a real-time strategy and puzzle video game developed and published by Nintendo for the GameCube.
    The game was a commercial success, and the first of the Pikmin series.
    """
    game: str = "Pikmin"
    web = PikminWeb()
    options_dataclass = PikminOptions
    options: PikminOptions

    item_name_to_id = item_name_to_id
    location_name_to_id = location_name_to_id

    def create_item(self, name: str) -> Item:
        data = item_table[name]
        return PikminItem(name, data.classification, self.item_name_to_id[name], self.player)

    def create_regions(self):
        # Create menu region
        menu_region = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu_region)

        # Create game regions and special locations
        for area in Areas:
            area_region = Region(area.value, self.player, self.multiworld)
            self.multiworld.regions.append(area_region)

        for loc_name, loc_data in location_table.items():
            if loc_data.area == "Special":
                location = PikminLocation(self.player, loc_name, loc_data.id, menu_region)
                menu_region.locations.append(location)
            else:
                region = self.multiworld.get_region(loc_data.area, self.player)
                location = PikminLocation(self.player, loc_name, loc_data.id, region)
                region.locations.append(location)

        # Connect regions
        impact_site = self.multiworld.get_region(Areas.IMPACT_SITE.value, self.player)
        forest_of_hope = self.multiworld.get_region(Areas.FOREST_HOPE.value, self.player)
        forest_navel = self.multiworld.get_region(Areas.FOREST_NAVEL.value, self.player)
        distant_spring = self.multiworld.get_region(Areas.DISTANT_SPRING.value, self.player)
        final_trial = self.multiworld.get_region(Areas.FINAL_TRIAL.value, self.player)

        menu_region.connect(impact_site, "New Game")
        impact_site.connect(forest_of_hope, "Go to The Forest of Hope")
        impact_site.connect(forest_navel, "Go to The Forest Navel")
        impact_site.connect(distant_spring, "Go to The Distant Spring")
        impact_site.connect(final_trial, "Go to The Final Trial")

    def create_items(self):
        item_pool = []
        
        # 1. Add all progression items, which are essential for world completion
        progression_item_names = get_progression_items()
        for name in progression_item_names:
            item_pool.append(self.create_item(name))

        # 2. Create a weighted list of non-progression items to fill the remaining spots
        filler_item_pool = []
        for name, data in item_table.items():
            if data.classification == ItemClassification.useful:
                filler_item_pool.extend([name] * 5)  # Useful items are somewhat common
            elif data.classification == ItemClassification.filler:
                filler_item_pool.extend([name] * 10) # Filler items are very common
            elif data.classification == ItemClassification.trap:
                filler_item_pool.append(name) # Traps are rare

        # 3. Fill the rest of the pool with items from the weighted list
        remaining_slots = len(location_table) - len(item_pool)
        for _ in range(remaining_slots):
            chosen_item_name = self.random.choice(filler_item_pool)
            item_pool.append(self.create_item(chosen_item_name))

        self.multiworld.itempool += item_pool

    def set_rules(self):
        set_rules(self)

    def generate_basic(self):
        # Set the victory condition
        self.multiworld.completion_condition[self.player] = lambda state: state.can_reach("Ship Repaired", "Location", self.player)

    def fill_slot_data(self) -> dict:
        return {
            "death_link": self.options.death_link.value,
        }
