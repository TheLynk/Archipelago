from enum import Enum

class ItemName:
    # Pikmin Types
    RED_PIKMIN = "Red Pikmin Discovery"
    BLUE_PIKMIN = "Blue Pikmin Discovery"
    YELLOW_PIKMIN = "Yellow Pikmin Discovery"
    WHITE_PIKMIN = "White Pikmin Discovery" # Assuming name from Pikmin 2
    PURPLE_PIKMIN = "Purple Pikmin Discovery" # Assuming name from Pikmin 2
    ROCK_PIKMIN = "Rock Pikmin Discovery" # Assuming name from Pikmin 3
    WINGED_PIKMIN = "Winged Pikmin Discovery" # Assuming name from Pikmin 3
    ICE_PIKMIN = "Ice Pikmin Discovery" # Assuming name from Pikmin 4
    GLOW_PIKMIN = "Glow Pikmin Discovery" # Assuming name from Pikmin 4

    # Ship Parts (Pikmin 1)
    MAIN_ENGINE = "Main Engine"
    POSITRON_GENERATOR = "Positron Generator"
    ETERNAL_FUEL_DYNAMO = "Eternal Fuel Dynamo"

    # Upgrades
    ROCKET_FIST = "Rocket Fist" # From Pikmin 3, but referenced in rules
    RUSH_BOOTS = "Rush Boots" # From Pikmin 3, but referenced in rules
    ULTRA_SPICY_SPRAY = "Spicy Spray"
    ULTRA_BITTER_SPRAY = "Bitter Spray"


class LocationName:
    # Pikmin 1 Locations from location_table
    ENGINE_IMPACT_SITE = "Engine - Impact Site"
    POSITRON_GENERATOR_IMPACT_SITE = "Positron Generator - Impact Site"
    # ... add all other locations if needed for future rules
    SHIP_REPAIRED = "Ship Repaired"


class RegionName(str, Enum):
    # Pikmin 1
    MENU = "Menu"
    IMPACT_SITE = "The Impact Site"
    FOREST_OF_HOPE = "The Forest of Hope"
    FOREST_NAVEL = "The Forest Navel"
    DISTANT_SPRING = "The Distant Spring"
    FINAL_TRIAL = "The Final Trial"

    # Pikmin 2 (referenced in Rules.py)
    VALLEY_OF_REPOSE = "Valley of Repose"
    AWAKENING_WOOD = "Awakening Wood"
    PERPLEXING_POOL = "Perplexing Pool"
    WISTFUL_WILD = "Wistful Wild"

    # Pikmin 3 (referenced in Rules.py)
    TROPICAL_WILDS = "Tropical Wilds"
    GARDEN_OF_HOPE = "Garden of Hope"
    DISTANT_TUNDRA = "Distant Tundra"
    TWILIGHT_RIVER = "Twilight River"
    FORMIDABLE_OAK = "Formidable Oak"