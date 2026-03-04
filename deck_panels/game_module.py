"""
Steam Deck Panels — shared imports and constants (RW2).

All dimension values that can change with set_size() (RENDER_WIDTH,
RENDER_HEIGHT, LEVEL_SIZE) are read dynamically from the view instance
at runtime, NOT imported here.  Only truly constant values live here.
"""

import sys

# Import the main game module so we can access its globals dynamically.
# At mod-load time these globals may still hold defaults (1920/1080/33);
# they get their real values when set_size() runs inside PyGameView.__init__().
import RiftWizard2 as rw2

PyGameView = rw2.PyGameView

try:
    from Level import Point
except ImportError:
    Point = rw2.Point

# These never change with set_size()
SPRITE_SIZE = 16
SCALE_FACTOR = 2
STATE_LEVEL = rw2.STATE_LEVEL
