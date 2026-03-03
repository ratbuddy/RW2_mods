"""
Floating Damage Numbers — a Rift Wizard 2 mod

Displays floating damage numbers above units when they take damage.
Numbers rise upward and fade out, tinted by damage type color.
Healing from negative resistance is shown in green with a "+" prefix.

Port note: RW2 uses SPRITE_SIZE=16 with a 2× scale to screen, so this mod
draws directly onto self.screen at full resolution after the scale pass.

Configuration constants are at the top of this file.
"""

import sys
import os
import random
import pygame

# ---------------------------------------------------------------------------
# Game module references
# ---------------------------------------------------------------------------
_game = sys.modules.get("__main__")
if _game is None:
    import RiftWizard2 as _game

PyGameView = getattr(_game, "PyGameView")
SPRITE_SIZE = getattr(_game, "SPRITE_SIZE", 16)

import Level as LevelModule

# ---------------------------------------------------------------------------
# Configuration — tweak these to your liking
# ---------------------------------------------------------------------------
FLOAT_SPEED = 1.0  # Pixels per frame to drift upward (screen-space)
TOTAL_FRAMES = 40  # Lifetime in frames (~1.3 sec at 30 FPS)
FADE_START_FRAC = 0.5  # Fraction of lifetime before fade begins
FONT_SIZE = 16  # Font size in pixels (drawn on screen at full res)
X_SCATTER = 10  # Max random horizontal offset (screen px)
Y_SCATTER = 6  # Max random vertical offset (screen px)
SHOW_ZERO_DAMAGE = False  # Show "0" when damage is fully resisted/blocked
OUTLINE = True  # Black outline for readability on any background
HEAL_COLOR = (66, 220, 66)

# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------
_floating_numbers = []  # Active FloatingNumber instances
_pending = []  # Queued during deal_damage, consumed in draw_level
_font = None
_last_level_id = None


def _get_font():
    """Lazily create the font (pygame must be initialised first)."""
    global _font
    if _font is None:
        try:
            path = os.path.join("rl_data", "PrintChar21.ttf")
            _font = pygame.font.Font(path, FONT_SIZE)
        except Exception:
            _font = pygame.font.Font(None, FONT_SIZE)
    return _font


# ---------------------------------------------------------------------------
# FloatingNumber — the visual element
# ---------------------------------------------------------------------------
class FloatingNumber:
    """A single floating number that drifts upward and fades out.

    Stores tile coordinates; pixel positions are computed at draw time
    using the view's current scale factors so they stay correct at any
    window size.
    """

    __slots__ = (
        "tile_x",
        "tile_y",
        "finished",
        "frame",
        "y_offset",
        "x_offset",
        "text_surf",
        "outline_surf",
    )

    def __init__(self, x, y, amount, color, prefix=""):
        self.tile_x = x
        self.tile_y = y
        self.finished = False
        self.frame = 0
        self.y_offset = float(random.randint(-Y_SCATTER, Y_SCATTER))
        self.x_offset = random.randint(-X_SCATTER, X_SCATTER)
        label = f"{prefix}{amount}"
        font = _get_font()
        self.text_surf = font.render(label, True, color)
        self.outline_surf = font.render(label, True, (0, 0, 0)) if OUTLINE else None

    def update_and_draw(self, surface, level_offset, sx, sy):
        """Advance animation and blit to *surface* (the screen).

        *level_offset* is the (x, y) pixel offset of the level_display
        subsurface inside whole_level_display.
        *sx* / *sy* are the scale factors from whole_level_display to screen.
        """
        if self.finished:
            return

        self.y_offset -= FLOAT_SPEED
        self.frame += 1

        # Alpha — full opacity until FADE_START_FRAC, then linear fade to 0
        fade_frame = int(TOTAL_FRAMES * FADE_START_FRAC)
        if self.frame > fade_frame:
            alpha = int(
                255
                * (1.0 - (self.frame - fade_frame) / max(1, TOTAL_FRAMES - fade_frame))
            )
        else:
            alpha = 255

        if alpha <= 0:
            self.finished = True
            return

        # Map tile centre to screen coordinates
        tile_cx = level_offset[0] + self.tile_x * SPRITE_SIZE + SPRITE_SIZE // 2
        tile_cy = level_offset[1] + self.tile_y * SPRITE_SIZE + SPRITE_SIZE // 2
        screen_cx = tile_cx * sx
        screen_cy = tile_cy * sy

        # Position text centred on the tile, offset by drift & scatter
        px = int(screen_cx - self.text_surf.get_width() // 2 + self.x_offset)
        py = int(screen_cy + self.y_offset)

        # Black outline (four cardinal offsets)
        if self.outline_surf:
            self.outline_surf.set_alpha(alpha)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                surface.blit(self.outline_surf, (px + dx, py + dy))

        # Main coloured text
        self.text_surf.set_alpha(alpha)
        surface.blit(self.text_surf, (px, py))

        if self.frame >= TOTAL_FRAMES:
            self.finished = True


# ---------------------------------------------------------------------------
# Hook: Level.deal_damage — record every damage event for display
# ---------------------------------------------------------------------------
_orig_deal_damage = LevelModule.Level.deal_damage


def _hooked_deal_damage(
    self, x, y, amount, damage_type, source, flash=True, redirect=False
):
    result = _orig_deal_damage(
        self, x, y, amount, damage_type, source, flash=flash, redirect=redirect
    )

    if result == 0 and not SHOW_ZERO_DAMAGE:
        return result

    # Determine colour from the damage type tag
    try:
        color = damage_type.color.to_tup()
    except Exception:
        color = (255, 255, 255)

    if result < 0:
        # Negative damage = healing via high resistance
        _pending.append(FloatingNumber(x, y, abs(result), HEAL_COLOR, prefix="+"))
    elif result > 0:
        _pending.append(FloatingNumber(x, y, result, color))
    elif SHOW_ZERO_DAMAGE:
        _pending.append(FloatingNumber(x, y, 0, (180, 180, 180)))

    return result


LevelModule.Level.deal_damage = _hooked_deal_damage


# ---------------------------------------------------------------------------
# Hook: PyGameView.draw_level — render floating numbers on the screen
#
# RW2 pipeline: draw_level draws to level_display (16 px/tile), then at the
# end scales whole_level_display 2× onto self.screen.  We call the original
# first, then blit floating numbers directly onto self.screen at full res
# so the text is crisp at any window size.
# ---------------------------------------------------------------------------
_orig_draw_level = PyGameView.draw_level


def _hooked_draw_level(self):
    global _last_level_id

    _orig_draw_level(self)

    # Don't draw during the game-over fade
    if getattr(self, "gameover_frames", 0) >= 8:
        return

    # Clear everything on level change so old numbers don't linger
    level_obj = getattr(getattr(self, "game", None), "cur_level", None)
    lid = id(level_obj) if level_obj else None
    if lid != _last_level_id:
        _floating_numbers.clear()
        _pending.clear()
        _last_level_id = lid

    # Compute scale factors: whole_level_display → screen
    wld = getattr(self, "whole_level_display", None)
    if wld is None:
        return
    sx = self.screen.get_width() / wld.get_width()
    sy = self.screen.get_height() / wld.get_height()

    # Offset of level_display within whole_level_display
    level_offset = self.level_display.get_offset()

    # Promote pending → active
    _floating_numbers.extend(_pending)
    _pending.clear()

    # Draw & advance every active number
    for fn in _floating_numbers:
        fn.update_and_draw(self.screen, level_offset, sx, sy)

    # Prune finished ones
    _floating_numbers[:] = [fn for fn in _floating_numbers if not fn.finished]


PyGameView.draw_level = _hooked_draw_level
