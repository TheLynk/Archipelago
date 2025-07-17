from worlds.AutoWorld import World
from .pikmin_world import PikminWorld

def launch():
    """Launch the Pikmin client"""
    from .client import launch
    launch()

# Export the world class
__all__ = ["PikminWorld", "launch"]