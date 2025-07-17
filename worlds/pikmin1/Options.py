from dataclasses import dataclass
from Options import Choice, Range, Toggle, DeathLink, DefaultOnToggle

class PikminGoal(Choice):
    """Objectif principal du jeu"""
    display_name = "Goal"
    option_defeat_emperor = 0
    option_collect_all_parts = 1
    option_30_day_challenge = 2
    default = 0

class StartingPikmin(Range):
    """Nombre de Pikmin rouges au début"""
    display_name = "Starting Red Pikmin"
    range_start = 1
    range_end = 50
    default = 5

class PikminMultiplier(Range):
    """Multiplicateur pour la croissance des Pikmin"""
    display_name = "Pikmin Growth Multiplier"
    range_start = 1
    range_end = 10
    default = 1

class DayTimeLimit(Range):
    """Limite de temps par jour (en minutes)"""
    display_name = "Day Time Limit"
    range_start = 5
    range_end = 30
    default = 13

class MaxDays(Range):
    """Nombre maximum de jours"""
    display_name = "Maximum Days"
    range_start = 15
    range_end = 50
    default = 30

class ShipPartsRequired(Range):
    """Nombre de pièces de vaisseau requises pour la victoire"""
    display_name = "Ship Parts Required"
    range_start = 15
    range_end = 30
    default = 25

class RandomizePikminColors(Toggle):
    """Randomiser les couleurs des Pikmin et leurs capacités"""
    display_name = "Randomize Pikmin Colors"
    default = False

class RandomizeAreas(Toggle):
    """Randomiser l'ordre d'accès aux zones"""
    display_name = "Randomize Area Access"
    default = False

class IncludeBosses(DefaultOnToggle):
    """Inclure les boss dans les vérifications d'emplacements"""
    display_name = "Include Boss Defeats"

class IncludePellets(DefaultOnToggle):
    """Inclure les Pellets dans les vérifications d'emplacements"""
    display_name = "Include Pellet Collection"

class IncludeEnemies(Toggle):
    """Inclure la défaite d'ennemis normaux"""
    display_name = "Include Enemy Defeats"
    default = False

class HardMode(Toggle):
    """Mode difficile avec moins de Pikmin et plus de défis"""
    display_name = "Hard Mode"
    default = False

class NoFlowerPikmin(Toggle):
    """Commencer sans Pikmin à fleurs"""
    display_name = "No Flower Pikmin Start"
    default = False

class FastGrowth(Toggle):
    """Croissance accélérée des Pikmin"""
    display_name = "Fast Pikmin Growth"
    default = False

class UnlimitedPikmin(Toggle):
    """Pas de limite sur le nombre de Pikmin"""
    display_name = "Unlimited Pikmin"
    default = False

class PikminDeathLink(DeathLink):
    """Lien de mort quand tous les Pikmin meurent"""
    display_name = "Death Link"

@dataclass
class PikminOptions:
    """Options de configuration pour Pikmin"""
    goal: PikminGoal
    starting_pikmin: StartingPikmin
    pikmin_multiplier: PikminMultiplier
    day_time_limit: DayTimeLimit
    max_days: MaxDays
    ship_parts_required: ShipPartsRequired
    randomize_pikmin_colors: RandomizePikminColors
    randomize_areas: RandomizeAreas
    include_bosses: IncludeBosses
    include_pellets: IncludePellets
    include_enemies: IncludeEnemies
    hard_mode: HardMode
    no_flower_pikmin: NoFlowerPikmin
    fast_growth: FastGrowth
    unlimited_pikmin: UnlimitedPikmin
    death_link: PikminDeathLink

# Groupes d'options pour l'interface
option_groups = [
    {
        "name": "Gameplay",
        "options": [
            "goal",
            "starting_pikmin",
            "pikmin_multiplier",
            "day_time_limit",
            "max_days",
            "ship_parts_required"
        ]
    },
    {
        "name": "Randomization",
        "options": [
            "randomize_pikmin_colors",
            "randomize_areas"
        ]
    },
    {
        "name": "Locations",
        "options": [
            "include_bosses",
            "include_pellets",
            "include_enemies"
        ]
    },
    {
        "name": "Difficulty",
        "options": [
            "hard_mode",
            "no_flower_pikmin",
            "fast_growth",
            "unlimited_pikmin",
            "death_link"
        ]
    }
]

# Presets pour différents styles de jeu
option_presets = {
    "Casual": {
        "goal": PikminGoal.option_defeat_emperor,
        "starting_pikmin": 10,
        "pikmin_multiplier": 2,
        "day_time_limit": 15,
        "max_days": 40,
        "ship_parts_required": 20,
        "hard_mode": False,
        "fast_growth": True,
        "unlimited_pikmin": True
    },
    "Normal": {
        "goal": PikminGoal.option_defeat_emperor,
        "starting_pikmin": 5,
        "pikmin_multiplier": 1,
        "day_time_limit": 13,
        "max_days": 30,
        "ship_parts_required": 25,
        "hard_mode": False,
        "fast_growth": False,
        "unlimited_pikmin": False
    },
    "Hard": {
        "goal": PikminGoal.option_collect_all_parts,
        "starting_pikmin": 3,
        "pikmin_multiplier": 1,
        "day_time_limit": 10,
        "max_days": 25,
        "ship_parts_required": 30,
        "hard_mode": True,
        "fast_growth": False,
        "unlimited_pikmin": False,
        "no_flower_pikmin": True
    },
    "Speedrun": {
        "goal": PikminGoal.option_30_day_challenge,
        "starting_pikmin": 1,
        "pikmin_multiplier": 1,
        "day_time_limit": 13,
        "max_days": 30,
        "ship_parts_required": 25,
        "hard_mode": True,
        "fast_growth": False,
        "unlimited_pikmin": False,
        "randomize_areas": True
    }
}