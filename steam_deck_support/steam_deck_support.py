"""
Steam Deck Panels Mod for Rift Wizard 2
========================================
Adds collapsible/slideable side panels and a zoomable/scrollable
level viewport for improved Steam Deck and small-screen playability.

Controls:
  F9  : Toggle both panels (collapse / expand)
  F10 : Toggle left panel (character / spells)
  F11 : Toggle right panel (examine / target info)
  F7  : Zoom in (bigger tiles, scrollable view)
  F8  : Zoom out
  Mouse wheel on level : Zoom in/out (when not targeting)

With controller_support mod:
  Back + LB        : Toggle left panel
  Back + RB        : Toggle right panel
  Back + Y         : Toggle both panels
  Back + D-pad Up  : Zoom in
  Back + D-pad Dn  : Zoom out
  Right stick      : Scroll camera when zoomed (and not targeting)

Panels slide smoothly; zoom uses post-process crop+scale of the level
surface so all effects/targeting/sprites work unchanged.
Works at all board sizes (1920×1080, 1600×900, 1366×768).

This is the entry point loaded by the game's mod system.
"""

# ---------------------------------------------------------------------------
#  Optional: force smallest board size for Steam Deck
# ---------------------------------------------------------------------------
# Set to True to use the small board (24×24 tiles, 1366×768 render).
# Recommended for the Steam Deck's 1280×800 native display — fewer tiles
# means larger sprites and better readability on a small screen.
# Set to False to let RW2 auto-detect based on your display resolution.
FORCE_SMALL_BOARD = True

if FORCE_SMALL_BOARD:
    import RiftWizard2 as _rw2

    if _rw2.SIZE is None:
        _rw2.set_size(_rw2.SIZE_SMALL)
        print("[Deck Panels] Forcing small board size (24×24) for Steam Deck")

from .patches import apply_patches
from .controller_hooks import try_integrate_controller

print("[Deck Panels] Loading Steam Deck panels + viewport mod...")
apply_patches()
try_integrate_controller()
print("[Deck Panels] Mod loaded successfully!")
print("[Deck Panels] Panels: F9/F10/F11 | Zoom: F7/F8/scroll wheel")
