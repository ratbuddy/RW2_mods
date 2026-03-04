"""
Steam Deck Panels — Monkey-patches for rendering and input (RW2).

Wraps:
  - draw_character()        → skip blit when left panel collapsed
  - draw_examine()          → skip blit when right panel collapsed
  - get_surface_pos()       → return animated positions for hit-testing
  - get_mouse_level_point() → inverse-transform through expanded viewport
  - draw_level()            → crop+scale for expansion/zoom, save to cache
  - draw_screen()           → compositor + toggle keys + zoom

When panels collapse the level display *expands* to fill the freed
screen width.  Tiles scale up uniformly; the viewport camera handles
scrolling.

RW2 draw order:
    draw_level → draw_character → draw_examine → draw_screen

The compositor runs inside draw_screen BEFORE the final flip:
  1. Blit expanded level surface (fills freed panel areas)
  2. Re-blit visible panels at animated positions on top
  3. Call original draw_screen (scales to real display + flip)

All dimensions are read from the view instance at runtime so the mod
works at every board size (1920×1080/33, 1600×900/28, 1366×768/24).

Keyboard shortcuts:
  F9          → toggle both panels
  F10         → toggle left panel
  F11         → toggle right panel
  F7 / F8     → zoom in / out
  Scroll Wheel on level → zoom in / out (when not targeting)
"""

import pygame

from . import panel_state as ps
from .viewport import viewport as vp
from .game_module import (
    PyGameView,
    Point,
    SPRITE_SIZE,
    SCALE_FACTOR,
    STATE_LEVEL,
)

# ---------------------------------------------------------------------------
#  Toggle keys  (users can change these)
# ---------------------------------------------------------------------------
TOGGLE_BOTH_KEY = pygame.K_F9
TOGGLE_LEFT_KEY = pygame.K_F10
TOGGLE_RIGHT_KEY = pygame.K_F11
ZOOM_IN_KEY = pygame.K_F7
ZOOM_OUT_KEY = pygame.K_F8


# ===========================================================================
#  Patch storage — keep originals so other mods can still chain
# ===========================================================================
_originals = {}


def _save(name):
    _originals[name] = getattr(PyGameView, name)


def _orig(name):
    return _originals[name]


# ===========================================================================
#  Helpers — all dimensions from the view instance, never module constants
# ===========================================================================

def _level_native(view):
    """Native level_display width in pixels (528 / 448 / 384)."""
    return view.level_display.get_width()


def _current_left_x(view):
    """Effective left-panel blit X (≤0 when sliding out)."""
    return ps.left_offset(view.h_margin)


def _current_right_x(view):
    """Effective right-panel blit X."""
    return ps.right_offset(view.screen.get_width(), view.h_margin)


def _level_needs_expansion():
    """True if at least one panel is not fully open."""
    return ps.left_panel.frac < 0.999 or ps.right_panel.frac < 0.999


def _get_level_dest_rect(view):
    """Return (x, y, w, h) of the expanded level area on screen.

    When both panels are fully open this is the normal level footprint.
    As panels collapse the rect grows toward the screen edges and tiles
    scale up uniformly.
    """
    hm = view.h_margin
    ln = _level_native(view)
    rh = view.screen.get_height()

    left_freed = hm * (1.0 - ps.left_panel.frac)
    right_freed = hm * (1.0 - ps.right_panel.frac)

    dest_x = int(hm - left_freed)
    dest_w = int(ln * SCALE_FACTOR + left_freed + right_freed)
    dest_h = rh
    return dest_x, 0, dest_w, dest_h


def _ensure_viewport_configured(view):
    """Reconfigure viewport if actual level dimensions differ."""
    ln = _level_native(view)
    ls = ln // SPRITE_SIZE
    if vp.level_px != ln or vp.level_size != ls:
        vp.reconfigure(ln, SPRITE_SIZE, ls)
        print(f"[Deck Panels] Viewport reconfigured: "
              f"level_px={ln}, level_size={ls}")


# ---------------------------------------------------------------------------
#  Expanded level cache — produced by _draw_level, consumed by compositor
# ---------------------------------------------------------------------------
_expanded_cache = {
    "active": False,
    "surface": None,
    "dest_x": 0,
    "dest_w": 0,
    "dest_h": 0,
}


# ===========================================================================
#  Patched methods
# ===========================================================================


def _panels_allowed(view):
    """True only in STATE_LEVEL.  All other states need full panels visible."""
    return getattr(view, 'state', None) == STATE_LEVEL


# ---- draw_character -------------------------------------------------------
def _draw_character(self):
    """Skip drawing left panel when fully collapsed (only in STATE_LEVEL)."""
    ps.tick()  # advance animation (safe to call multiple times per frame)
    if ps.left_panel.is_fully_closed and _panels_allowed(self):
        self.character_display.fill((0, 0, 0))
        return
    # Call original — it renders into character_display and blits at (0, 0).
    # The compositor will overwrite this blit and re-blit at the animated
    # position if expansion is active.
    _orig("draw_character")(self)


# ---- draw_examine ---------------------------------------------------------
def _draw_examine(self):
    """Skip drawing right panel when fully collapsed (only in STATE_LEVEL)."""
    if ps.right_panel.is_fully_closed and _panels_allowed(self):
        self.examine_display.fill((0, 0, 0))
        return
    # Call original — it renders into examine_display and blits on the right.
    # The compositor handles repositioning when panels are sliding.
    _orig("draw_examine")(self)


# ---- get_surface_pos (used by make_content_rect for hit-testing) -----------
def _get_surface_pos(self, surf):
    """Return the *current animated* blit position of a surface so that
    make_content_rect hit-testing works correctly during slides."""
    if surf == self.middle_menu_display:
        return (self.h_margin, 0)
    elif surf == self.examine_display:
        return (_current_right_x(self), 0)
    elif surf == self.character_display:
        return (_current_left_x(self), 0)
    else:
        return (0, 0)


# ---- get_mouse_level_point override ----------------------------------------
def _get_mouse_level_point(self):
    """Translate mouse position through the expanded viewport.

    When the level is expanded or zoomed, screen coordinates must be
    mapped through the viewport's inverse transform to get tile coords.
    """
    expanded = _level_needs_expansion()

    if not vp.is_zoomed and not expanded:
        return _orig("get_mouse_level_point")(self)

    x, y = self.get_mouse_pos()
    dest_x, dest_y, dest_w, dest_h = _get_level_dest_rect(self)

    result = vp.screen_to_tile(x, y, dest_x, dest_y, dest_w, dest_h)
    if result is None:
        return None
    return Point(result[0], result[1])


# ---- get_mouse_rel — suppress phantom mouse during controller targeting ---
def _get_mouse_rel(self):
    """Return (0, 0) when the controller is actively providing directional
    input while a spell is being targeted.

    On Steam Deck / SDL2, the controller stick can generate phantom
    pygame.mouse.get_rel() movement which stomps the keyboard-set
    cur_spell_target each frame (process_level_input line ~2463).

    We detect the controller being active by checking for the
    _ctrl_injected_frame attribute set by the controller_support mod.
    """
    import sys
    ctrl_mod = sys.modules.get("mods.controller_support.controller_support")
    if ctrl_mod is not None:
        ctrl = getattr(ctrl_mod, "ctrl", None)
        if ctrl is not None and getattr(ctrl, "connected", False):
            # If a spell is being targeted, suppress mouse rel
            # to prevent it from overriding the stick-driven cursor
            if getattr(self, 'cur_spell', None) is not None:
                return (0, 0)
            # Also suppress during deploy targeting
            if getattr(self, 'game', None) and getattr(self.game, 'deploying', False):
                return (0, 0)
    return _orig("get_mouse_rel")(self)


# ===========================================================================
#  draw_level wrapper — crop + scale for expansion / zoom
# ===========================================================================
def _draw_level(self):
    """Render the level, then crop + scale for expansion/zoom.

    The original draw_level renders tiles at 16 px into level_display
    (subsurface of whole_level_display), then 2× scales the whole thing
    onto self.screen.  After it returns, level_display still holds the
    native-res content.

    When panels are collapsed or zoom is active we crop from level_display
    through the viewport, upscale to the expanded destination, and save
    the result to _expanded_cache.  The compositor in draw_screen blits
    it to screen later (after panels have drawn).
    """
    _ensure_viewport_configured(self)

    # Tick the viewport camera (auto-follow player)
    player = getattr(self.game, "p1", None) if self.game else None
    if player:
        vp.tick(player.x, player.y)
    else:
        vp.tick()

    expanded = _level_needs_expansion()

    # Fast path: no expansion and no zoom — original rendering is fine
    if not expanded and not vp.is_zoomed:
        _orig("draw_level")(self)
        _expanded_cache["active"] = False
        return

    # --- Expansion / zoom path ---
    # Let original render (fills screen with 2× level).
    # level_display retains native-res content for cropping.
    _orig("draw_level")(self)

    ln = _level_native(self)
    dest_x, _, dest_w, dest_h = _get_level_dest_rect(self)

    # Source rect from viewport (uniform scaling based on width)
    sx, sy, src_w, src_h = vp.get_source_rect(dest_w, dest_h)

    # Clamp to level_display bounds
    clip_x = max(0, int(sx))
    clip_y = max(0, int(sy))
    clip_r = min(ln, int(sx + src_w + 0.5))
    clip_b = min(ln, int(sy + src_h + 0.5))
    clip_w = max(1, clip_r - clip_x)
    clip_h = max(1, clip_b - clip_y)

    try:
        cropped = self.level_display.subsurface(
            pygame.Rect(clip_x, clip_y, clip_w, clip_h)
        )
    except ValueError:
        _expanded_cache["active"] = False
        return

    # Scale crop to fill destination (uniform scale)
    scale_x = dest_w / src_w if src_w > 0 else 1
    scale_y = dest_h / src_h if src_h > 0 else 1
    scaled_w = max(1, int(clip_w * scale_x))
    scaled_h = max(1, int(clip_h * scale_y))
    scaled = pygame.transform.smoothscale(cropped, (scaled_w, scaled_h))

    # Blit offset for camera overshoot past level edges
    blit_x = int((clip_x - sx) * scale_x)
    blit_y = int((clip_y - sy) * scale_y)

    # Build the expanded surface (reuse allocation when possible)
    expanded_surf = _expanded_cache.get("surface")
    if expanded_surf is None or expanded_surf.get_size() != (dest_w, dest_h):
        expanded_surf = pygame.Surface((dest_w, dest_h))
    expanded_surf.fill((0, 0, 0))
    expanded_surf.blit(scaled, (blit_x, blit_y))

    _expanded_cache["active"] = True
    _expanded_cache["surface"] = expanded_surf
    _expanded_cache["dest_x"] = dest_x
    _expanded_cache["dest_w"] = dest_w
    _expanded_cache["dest_h"] = dest_h


# ===========================================================================
#  draw_screen wrapper — compositor + key/zoom handling
# ===========================================================================
def _draw_screen_wrapper(original):
    """Wrap draw_screen() to composite expanded level + panels, and to
    check toggle/zoom keys and mouse-wheel zoom."""

    def wrapper(self, color=None):
        ps.tick()

        # ---- Auto-expand panels when not in STATE_LEVEL ----
        # Prevents controls getting trapped in a hidden panel
        # (e.g. char sheet, shop, confirm dialogs).
        if not _panels_allowed(self):
            if not ps.left_panel.is_fully_open or not ps.right_panel.is_fully_open:
                ps.left_panel.show()
                ps.right_panel.show()
                ps.left_panel._frac = 1.0
                ps.right_panel._frac = 1.0
                _expanded_cache["active"] = False

        # ---- Key / mouse-wheel handling ----
        for evt in getattr(self, "events", []):
            if evt.type == pygame.KEYDOWN:
                if evt.key == TOGGLE_BOTH_KEY:
                    ps.toggle_both()
                elif evt.key == TOGGLE_LEFT_KEY:
                    ps.toggle_left()
                elif evt.key == TOGGLE_RIGHT_KEY:
                    ps.toggle_right()
                elif evt.key == ZOOM_IN_KEY:
                    vp.zoom_in()
                elif evt.key == ZOOM_OUT_KEY:
                    vp.zoom_out()
            elif evt.type == pygame.MOUSEWHEEL:
                mx, my = self.get_mouse_pos()
                dest_x, _, dest_w, dest_h = _get_level_dest_rect(self)
                in_level = dest_x <= mx < dest_x + dest_w and 0 <= my < dest_h
                has_spell = getattr(self, "cur_spell", None) is not None
                if in_level and not has_spell:
                    if evt.y > 0:
                        vp.zoom_in()
                    elif evt.y < 0:
                        vp.zoom_out()

        # ---- Compositor ----
        # By this point draw_level, draw_character, and draw_examine have
        # all run.  If expansion is active, layer everything correctly:
        #   1. Blit expanded level (fills freed panel areas)
        #   2. Re-blit visible panels at animated positions on top
        if _expanded_cache.get("active"):
            surf = _expanded_cache["surface"]
            dest_x = _expanded_cache["dest_x"]

            # Expanded level fills the center + freed side areas
            self.screen.blit(surf, (dest_x, 0))

            # Panels on top at their animated slide positions
            if not ps.left_panel.is_fully_closed:
                self.screen.blit(
                    self.character_display, (_current_left_x(self), 0)
                )
            if not ps.right_panel.is_fully_closed:
                self.screen.blit(
                    self.examine_display, (_current_right_x(self), 0)
                )

        return original(self, color)

    wrapper.__name__ = original.__name__
    wrapper.__qualname__ = original.__qualname__
    return wrapper


# ===========================================================================
#  Click-region margin adjustment
# ===========================================================================
def _make_click_margin_wrapper(original):
    """Temporarily reduce self.h_margin for click-region tests when the
    left panel is collapsed so clicks in the expanded level area reach
    the level instead of the (hidden) character panel."""

    def wrapper(self, *args, **kwargs):
        saved = self.h_margin

        if ps.left_panel.is_fully_closed:
            self.h_margin = 0
        elif not ps.left_panel.is_fully_open:
            self.h_margin = ps.left_panel.effective_width(saved)

        try:
            return original(self, *args, **kwargs)
        finally:
            self.h_margin = saved

    wrapper.__name__ = original.__name__
    wrapper.__qualname__ = original.__qualname__
    return wrapper


# ===========================================================================
#  Apply all patches
# ===========================================================================
def apply_patches():
    """Monkey-patch PyGameView with all deck-panel overrides."""

    for name in [
        "draw_character",
        "draw_examine",
        "get_surface_pos",
        "get_mouse_level_point",
        "get_mouse_rel",
        "draw_screen",
        "draw_level",
    ]:
        _save(name)

    PyGameView.draw_character = _draw_character
    PyGameView.draw_examine = _draw_examine
    PyGameView.get_surface_pos = _get_surface_pos
    PyGameView.get_mouse_level_point = _get_mouse_level_point
    PyGameView.get_mouse_rel = _get_mouse_rel
    PyGameView.draw_level = _draw_level

    PyGameView.draw_screen = _draw_screen_wrapper(_originals["draw_screen"])

    for name in [
        "process_level_input",
        "process_examine_panel_input",
    ]:
        orig = getattr(PyGameView, name, None)
        if orig:
            _save(name)
            setattr(PyGameView, name, _make_click_margin_wrapper(orig))

    print("[Deck Panels] Rendering + viewport + expansion patches applied")
