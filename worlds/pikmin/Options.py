from dataclasses import dataclass
from Options import Choice, DefaultOnToggle, Range, Toggle

class PikminDifficulty(Choice):
    """Difficulté du jeu"""
    display_name = "Difficulty"
    option_easy = 0
    option_normal = 1
    option_hard = 2
    default = 1

class RandomizeShipParts(DefaultOnToggle):
    """Randomise les pièces de vaisseau"""
    display_name = "Randomize Ship Parts"

class RandomizePikminTypes(Toggle):
    """Randomise les types de Pikmin disponibles"""
    display_name = "Randomize Pikmin Types"

class MinimumShipParts(Range):
    """Nombre minimum de pièces de vaisseau requises pour terminer"""
    display_name = "Minimum Ship Parts Required"
    range_start = 25
    range_end = 30
    default = 30

class StartingPikminCount(Range):
    """Nombre de Pikmin au départ"""
    display_name = "Starting Pikmin Count"
    range_start = 5
    range_end = 100
    default = 20

class RandomizeEnemies(Toggle):
    """Randomise les ennemis"""
    display_name = "Randomize Enemies"

class RandomizeTreasures(DefaultOnToggle):
    """Randomise les trésors et pellets"""
    display_name = "Randomize Treasures"

@dataclass
class PikminOptions:
    """Options pour Pikmin"""
    difficulty: PikminDifficulty
    randomize_ship_parts: RandomizeShipParts
    randomize_pikmin_types: RandomizePikminTypes
    minimum_ship_parts: MinimumShipParts
    starting_pikmin_count: StartingPikminCount
    randomize_enemies: RandomizeEnemies
    randomize_treasures: RandomizeTreasures