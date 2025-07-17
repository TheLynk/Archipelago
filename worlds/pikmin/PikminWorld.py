from worlds.AutoWorld import World
from .Items import item_name_to_id
from .Locations import location_name_to_id

class PikminWorld(World):
    game: str = "Pikmin"
    item_name_to_id = item_name_to_id
    location_name_to_id = location_name_to_id

    def generate_early(self):
        self.locations = [{"name": name, "item": None} for name in location_name_to_id.keys()]
