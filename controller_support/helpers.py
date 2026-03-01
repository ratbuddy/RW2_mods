"""
Controller Support — Event-creation helpers.

Small functions used by both browse.py and injection.py, factored out here
to avoid circular imports.
"""

import pygame

from .game_module import (
    KEY_BIND_UP, KEY_BIND_DOWN, KEY_BIND_LEFT, KEY_BIND_RIGHT,
    KEY_BIND_UP_RIGHT, KEY_BIND_UP_LEFT, KEY_BIND_DOWN_RIGHT, KEY_BIND_DOWN_LEFT,
)

# Direction → KEY_BIND lookup
_DIR_MAP = {
    (0, -1):  KEY_BIND_UP,
    (0,  1):  KEY_BIND_DOWN,
    (-1, 0):  KEY_BIND_LEFT,
    (1,  0):  KEY_BIND_RIGHT,
    (1, -1):  KEY_BIND_UP_RIGHT,
    (-1, -1): KEY_BIND_UP_LEFT,
    (1,  1):  KEY_BIND_DOWN_RIGHT,
    (-1, 1):  KEY_BIND_DOWN_LEFT,
}


def make_key_event(key, event_type=pygame.KEYDOWN):
    """Create a synthetic pygame keyboard event."""
    return pygame.event.Event(event_type, key=key)


def direction_to_key_bind(dx, dy):
    """Convert a digital direction (dx, dy) to the appropriate KEY_BIND constant."""
    return _DIR_MAP.get((dx, dy))


def get_key_for_bind(view, bind):
    """Return the first bound pygame key for a KEY_BIND constant, or None."""
    keys = view.key_binds.get(bind, [None, None])
    for k in keys:
        if k is not None:
            return k
    return None
