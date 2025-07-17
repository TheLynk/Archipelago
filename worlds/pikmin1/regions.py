from BaseClasses import Region, Entrance
from .locations import PikminLocation, locations_by_region, location_table

def create_regions(multiworld, player: int):
    """Create all regions for Pikmin world"""
    
    # Région de menu (toujours accessible)
    menu_region = Region("Menu", player, multiworld)
    multiworld.regions.append(menu_region)
    
    # Zone d'impact (région de départ)
    impact_site = Region("Impact Site", player, multiworld)
    impact_site.locations = [
        PikminLocation(player, loc_name, location_table[loc_name].id, impact_site)
        for loc_name in locations_by_region["Impact Site"]
    ]
    multiworld.regions.append(impact_site)
    
    # Forêt de l'Espoir
    forest_hope = Region("Forest of Hope", player, multiworld)
    forest_hope.locations = [
        PikminLocation(player, loc_name, location_table[loc_name].id, forest_hope)
        for loc_name in locations_by_region["Forest of Hope"]
    ]
    multiworld.regions.append(forest_hope)
    
    # Caverne de la Flamme
    forest_navel = Region("Forest Navel", player, multiworld)
    forest_navel.locations = [
        PikminLocation(player, loc_name, location_table[loc_name].id, forest_navel)
        for loc_name in locations_by_region["Forest Navel"]
    ]
    multiworld.regions.append(forest_navel)
    
    # Rivage Lointain
    distant_spring = Region("Distant Spring", player, multiworld)
    distant_spring.locations = [
        PikminLocation(player, loc_name, location_table[loc_name].id, distant_spring)
        for loc_name in locations_by_region["Distant Spring"]
    ]
    multiworld.regions.append(distant_spring)
    
    # Épreuve Finale
    final_trial = Region("Final Trial", player, multiworld)
    final_trial.locations = [
        PikminLocation(player, loc_name, location_table[loc_name].id, final_trial)
        for loc_name in locations_by_region["Final Trial"]
    ]
    multiworld.regions.append(final_trial)
    
    # Connexions entre régions
    create_region_connections(multiworld, player)

def create_region_connections(multiworld, player: int):
    """Create connections between regions"""
    
    # Connexion du menu vers la zone d'impact
    menu_to_impact = Entrance(player, "Start Game", multiworld.get_region("Menu", player))
    menu_to_impact.connect(multiworld.get_region("Impact Site", player))
    multiworld.get_region("Menu", player).exits.append(menu_to_impact)
    
    # Zone d'impact vers Forêt de l'Espoir
    impact_to_forest = Entrance(player, "To Forest of Hope", multiworld.get_region("Impact Site", player))
    impact_to_forest.connect(multiworld.get_region("Forest of Hope", player))
    multiworld.get_region("Impact Site", player).exits.append(impact_to_forest)
    
    # Forêt de l'Espoir vers Caverne de la Flamme
    forest_to_navel = Entrance(player, "To Forest Navel", multiworld.get_region("Forest of Hope", player))
    forest_to_navel.connect(multiworld.get_region("Forest Navel", player))
    multiworld.get_region("Forest of Hope", player).exits.append(forest_to_navel)
    
    # Caverne de la Flamme vers Rivage Lointain
    navel_to_spring = Entrance(player, "To Distant Spring", multiworld.get_region("Forest Navel", player))
    navel_to_spring.connect(multiworld.get_region("Distant Spring", player))
    multiworld.get_region("Forest Navel", player).exits.append(navel_to_spring)
    
    # Rivage Lointain vers Épreuve Finale
    spring_to_final = Entrance(player, "To Final Trial", multiworld.get_region("Distant Spring", player))
    spring_to_final.connect(multiworld.get_region("Final Trial", player))
    multiworld.get_region("Distant Spring", player).exits.append(spring_to_final)
    
    # Connexions de retour (optionnelles)
    forest_to_impact = Entrance(player, "Back to Impact Site", multiworld.get_region("Forest of Hope", player))
    forest_to_impact.connect(multiworld.get_region("Impact Site", player))
    multiworld.get_region("Forest of Hope", player).exits.append(forest_to_impact)