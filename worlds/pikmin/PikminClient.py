from worlds.AutoWorld import World
from .Items import item_name_to_id
from .Locations import locations

class PikminWorld(World):
    game: str = "Pikmin"
    item_name_to_id = item_name_to_id

    def generate_early(self):
        self.locations = locations
