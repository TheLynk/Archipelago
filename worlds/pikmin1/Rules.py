from BaseClasses import MultiWorld
from worlds.generic.Rules import add_rule, set_rule
from .locations import location_table

def set_pikmin_rules(multiworld: MultiWorld, player: int):
    """Set up all rules for Pikmin world"""
    
    # Règles d'accès aux régions
    set_region_rules(multiworld, player)
    
    # Règles d'accès aux emplacements
    set_location_rules(multiworld, player)
    
    # Règles de victoire
    set_victory_rules(multiworld, player)

def set_region_rules(multiworld: MultiWorld, player: int):
    """Set rules for accessing regions"""
    
    # La zone d'impact est toujours accessible depuis le menu
    # Pas de règle nécessaire
    
    # Forêt de l'Espoir : accessible après avoir collecté suffisamment de Pikmin rouges
    add_rule(multiworld.get_entrance("To Forest of Hope", player),
             lambda state: state.count("Red Pikmin Seed", player) >= 1)
    
    # Caverne de la Flamme : nécessite des Pikmin jaunes
    add_rule(multiworld.get_entrance("To Forest Navel", player),
             lambda state: state.count("Yellow Pikmin Seed", player) >= 1)
    
    # Rivage Lointain : nécessite des Pikmin bleus
    add_rule(multiworld.get_entrance("To Distant Spring", player),
             lambda state: state.count("Blue Pikmin Seed", player) >= 1)
    
    # Épreuve Finale : nécessite plusieurs pièces de vaisseau
    add_rule(multiworld.get_entrance("To Final Trial", player),
             lambda state: state.count("Ship Part", player) >= 15)

def set_location_rules(multiworld: MultiWorld, player: int):
    """Set rules for accessing locations"""
    
    # Règles pour les emplacements de la Zone d'Impact
    add_rule(multiworld.get_location("Impact Site - Red Pikmin Discovery", player),
             lambda state: True)  # Toujours accessible
    
    add_rule(multiworld.get_location("Impact Site - Main Engine", player),
             lambda state: state.count("Red Pikmin Seed", player) >= 5)
    
    # Règles basées sur le nombre de Pikmin rouges
    add_rule(multiworld.get_location("Collect 10 Red Pikmin", player),
             lambda state: state.count("Red Pikmin Seed", player) >= 1)
    
    add_rule(multiworld.get_location("Collect 25 Red Pikmin", player),
             lambda state: state.count("Red Pikmin Seed", player) >= 3)
    
    add_rule(multiworld.get_location("Collect 50 Red Pikmin", player),
             lambda state: state.count("Red Pikmin Seed", player) >= 5)
    
    add_rule(multiworld.get_location("Collect 100 Red Pikmin", player),
             lambda state: state.count("Red Pikmin Seed", player) >= 10)
    
    # Règles pour la Forêt de l'Espoir
    add_rule(multiworld.get_location("Forest of Hope - Yellow Pikmin Discovery", player),
             lambda state: state.count("Red Pikmin Seed", player) >= 2)
    
    add_rule(multiworld.get_location("Forest of Hope - Eternal Fuel Dynamo", player),
             lambda state: (state.count("Red Pikmin Seed", player) >= 3 and 
                          state.count("Yellow Pikmin Seed", player) >= 1))
    
    add_rule(multiworld.get_location("Forest of Hope - Whimsical Radar", player),
             lambda state: state.count("Yellow Pikmin Seed", player) >= 2)
    
    # Règles pour la Caverne de la Flamme
    add_rule(multiworld.get_location("Forest Navel - Blue Pikmin Discovery", player),
             lambda state: (state.count("Red Pikmin Seed", player) >= 3 and
                          state.count("Yellow Pikmin Seed", player) >= 2))
    
    add_rule(multiworld.get_location("Forest Navel - Gravity Machine", player),
             lambda state: (state.count("Red Pikmin Seed", player) >= 5 and
                          state.count("Yellow Pikmin Seed", player) >= 3 and
                          state.count("Blue Pikmin Seed", player) >= 1))
    
    # Règles pour le Rivage Lointain
    add_rule(multiworld.get_location("Distant Spring - First Area", player),
             lambda state: state.count("Blue Pikmin Seed", player) >= 1)
    
    add_rule(multiworld.get_location("Distant Spring - Libra", player),
             lambda state: (state.count("Red Pikmin Seed", player) >= 5 and
                          state.count("Yellow Pikmin Seed", player) >= 3 and
                          state.count("Blue Pikmin Seed", player) >= 3))
    
    # Règles pour les boss
    add_rule(multiworld.get_location("Defeat Armored Cannon Larva", player),
             lambda state: state.count("Red Pikmin Seed", player) >= 3)
    
    add_rule(multiworld.get_location("Defeat Beady Long Legs", player),
             lambda state: (state.count("Red Pikmin Seed", player) >= 5 and
                          state.count("Yellow Pikmin Seed", player) >= 2))
    
    add_rule(multiworld.get_location("Defeat Puffstool", player),
             lambda state: (state.count("Red Pikmin Seed", player) >= 5 and
                          state.count("Yellow Pikmin Seed", player) >= 3 and
                          state.count("Blue Pikmin Seed", player) >= 2))
    
    add_rule(multiworld.get_location("Defeat Emperor Bulblax", player),
             lambda state: (state.count("Red Pikmin Seed", player) >= 10 and
                          state.count("Yellow Pikmin Seed", player) >= 5 and
                          state.count("Blue Pikmin Seed", player) >= 5 and
                          state.count("Ship Part", player) >= 20))
    
    # Règles pour la progression
    add_rule(multiworld.get_location("First Day Complete", player),
             lambda state: state.count("Red Pikmin Seed", player) >= 2)
    
    add_rule(multiworld.get_location("Discover Yellow Pikmin", player),
             lambda state: state.count("Red Pikmin Seed", player) >= 2)
    
    add_rule(multiworld.get_location("Discover Blue Pikmin", player),
             lambda state: (state.count("Red Pikmin Seed", player) >= 3 and
                          state.count("Yellow Pikmin Seed", player) >= 2))

def set_victory_rules(multiworld: MultiWorld, player: int):
    """Set rules for victory condition"""
    
    # La victoire nécessite de battre l'Emperor Bulblax
    add_rule(multiworld.get_location("Defeat Emperor Bulblax", player),
             lambda state: (state.count("Red Pikmin Seed", player) >= 10 and
                          state.count("Yellow Pikmin Seed", player) >= 5 and
                          state.count("Blue Pikmin Seed", player) >= 5 and
                          state.count("Ship Part", player) >= 25 and
                          state.count("Engine", player) >= 1 and
                          state.count("Main Engine", player) >= 1))

def has_pikmin_type(state, player: int, pikmin_type: str, count: int = 1) -> bool:
    """Check if player has access to a specific type of Pikmin"""
    seed_name = f"{pikmin_type} Pikmin Seed"
    return state.count(seed_name, player) >= count

def can_access_area(state, player: int, area: str) -> bool:
    """Check if player can access a specific area"""
    area_requirements = {
        "Impact Site": lambda s: True,
        "Forest of Hope": lambda s: has_pikmin_type(s, player, "Red", 1),
        "Forest Navel": lambda s: has_pikmin_type(s, player, "Yellow", 1),
        "Distant Spring": lambda s: has_pikmin_type(s, player, "Blue", 1),
        "Final Trial": lambda s: state.count("Ship Part", player) >= 15
    }
    
    return area_requirements.get(area, lambda s: False)(state)

def can_defeat_boss(state, player: int, boss: str) -> bool:
    """Check if player can defeat a specific boss"""
    boss_requirements = {
        "Armored Cannon Larva": lambda s: has_pikmin_type(s, player, "Red", 3),
        "Beady Long Legs": lambda s: (has_pikmin_type(s, player, "Red", 5) and 
                                     has_pikmin_type(s, player, "Yellow", 2)),
        "Puffstool": lambda s: (has_pikmin_type(s, player, "Red", 5) and
                               has_pikmin_type(s, player, "Yellow", 3) and
                               has_pikmin_type(s, player, "Blue", 2)),
        "Emperor Bulblax": lambda s: (has_pikmin_type(s, player, "Red", 10) and
                                     has_pikmin_type(s, player, "Yellow", 5) and
                                     has_pikmin_type(s, player, "Blue", 5) and
                                     state.count("Ship Part", player) >= 20)
    }
    
    return boss_requirements.get(boss, lambda s: False)(state)