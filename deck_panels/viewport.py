"""
Steam Deck Panels — Viewport (zoom + scroll) state for RW2.

Manages a camera that shows a zoomed-in rectangular portion of the
33×33 level grid.  The level is rendered at native SPRITE_SIZE (16 px)
into level_display (528×528), then the viewport rectangle is cropped
and scaled up.

Right stick scrolls the camera.  Camera auto-centers on the player
when the player moves.  Zoom level is configurable.
"""

import time

# ---------------------------------------------------------------------------
#  Configuration
# ---------------------------------------------------------------------------

DEFAULT_ZOOM = 1.0
MIN_ZOOM = 1.0
MAX_ZOOM = 2.5
ZOOM_STEP = 0.25

# Camera scroll speed (pixels of level_display per second at zoom=1)
SCROLL_SPEED = 400.0

# Smooth camera follow
CAMERA_LERP_SPEED = 12.0

# How far past the edge the camera can go
EDGE_PADDING = 15


class Viewport:
    """Tracks zoom level and camera centre (in level_display pixel coords)."""

    def __init__(self, level_px=528, sprite_size=16, level_size=33):
        self.level_px = level_px
        self.sprite_size = sprite_size
        self.level_size = level_size

        self.zoom = DEFAULT_ZOOM

        half = level_px / 2.0
        self.cam_x = half
        self.cam_y = half

        self.target_x = half
        self.target_y = half

        self._last_time = time.monotonic()
        self._last_player_pos = None

    # ------------------------------------------------------------------
    #  Reconfigure for different board sizes
    # ------------------------------------------------------------------
    def reconfigure(self, level_px, sprite_size=16, level_size=33):
        """Update dimensions if the actual board size differs from init."""
        if (self.level_px == level_px and self.sprite_size == sprite_size
                and self.level_size == level_size):
            return  # no change
        self.level_px = level_px
        self.sprite_size = sprite_size
        self.level_size = level_size
        half = level_px / 2.0
        self.cam_x = half
        self.cam_y = half
        self.target_x = half
        self.target_y = half
        self._last_player_pos = None

    # ------------------------------------------------------------------
    #  Zoom
    # ------------------------------------------------------------------
    def zoom_in(self):
        self.zoom = min(self.zoom + ZOOM_STEP, MAX_ZOOM)

    def zoom_out(self):
        self.zoom = max(self.zoom - ZOOM_STEP, MIN_ZOOM)

    def set_zoom(self, z):
        self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, z))

    @property
    def is_zoomed(self):
        return self.zoom > 1.001

    # ------------------------------------------------------------------
    #  Camera
    # ------------------------------------------------------------------
    def center_on_tile(self, tx, ty, instant=False):
        self.target_x = (tx + 0.5) * self.sprite_size
        self.target_y = (ty + 0.5) * self.sprite_size
        if instant:
            self.cam_x = self.target_x
            self.cam_y = self.target_y

    def scroll(self, dx, dy, dt):
        self.target_x += dx * SCROLL_SPEED * dt
        self.target_y += dy * SCROLL_SPEED * dt

    def tick(self, player_x=None, player_y=None):
        now = time.monotonic()
        dt = min(now - self._last_time, 0.1)
        self._last_time = now

        if player_x is not None and player_y is not None:
            pos = (player_x, player_y)
            if self._last_player_pos is not None and pos != self._last_player_pos:
                self.center_on_tile(player_x, player_y)
            self._last_player_pos = pos

        self._clamp_target()

        t = min(1.0, CAMERA_LERP_SPEED * dt)
        self.cam_x += (self.target_x - self.cam_x) * t
        self.cam_y += (self.target_y - self.cam_y) * t

    def _clamp_target(self):
        lo = -EDGE_PADDING
        hi = self.level_px + EDGE_PADDING
        self.target_x = max(lo, min(hi, self.target_x))
        self.target_y = max(lo, min(hi, self.target_y))

    # ------------------------------------------------------------------
    #  Viewport rectangle (in level_display pixel coords)
    # ------------------------------------------------------------------
    def get_source_rect(self, dest_w, dest_h):
        """Return (x, y, w, h) of the crop rectangle on level_display.

        Scaling is uniform based on fitting level_px into dest_w at the
        current zoom.  When dest is wider than the level (panels collapsed)
        tiles get proportionally bigger, and fewer tiles are visible
        vertically.
        """
        uniform_scale = dest_w * self.zoom / self.level_px
        src_w = dest_w / uniform_scale
        src_h = dest_h / uniform_scale

        sx = self.cam_x - src_w / 2.0
        sy = self.cam_y - src_h / 2.0

        sx = max(-EDGE_PADDING, min(self.level_px + EDGE_PADDING - src_w, sx))
        sy = max(-EDGE_PADDING, min(self.level_px + EDGE_PADDING - src_h, sy))

        return sx, sy, src_w, src_h

    # ------------------------------------------------------------------
    #  Coordinate transforms
    # ------------------------------------------------------------------
    def screen_to_level_px(self, screen_x, screen_y, dest_x, dest_y, dest_w, dest_h):
        sx, sy, src_w, src_h = self.get_source_rect(dest_w, dest_h)

        frac_x = (screen_x - dest_x) / dest_w if dest_w else 0
        frac_y = (screen_y - dest_y) / dest_h if dest_h else 0

        level_px_x = sx + frac_x * src_w
        level_px_y = sy + frac_y * src_h

        return level_px_x, level_px_y

    def screen_to_tile(self, screen_x, screen_y, dest_x, dest_y, dest_w, dest_h):
        lpx, lpy = self.screen_to_level_px(
            screen_x, screen_y, dest_x, dest_y, dest_w, dest_h
        )
        tx = int(lpx // self.sprite_size)
        ty = int(lpy // self.sprite_size)

        if tx < 0 or ty < 0 or tx >= self.level_size or ty >= self.level_size:
            return None
        return tx, ty


# ---------------------------------------------------------------------------
#  Global instance  (created with defaults — reconfigured at first draw)
# ---------------------------------------------------------------------------
viewport = Viewport(
    level_px=33 * 16,   # 528 — overridden by patches._ensure_viewport_configured
    sprite_size=16,
    level_size=33,
)


def reset():
    """Reset to defaults.  reconfigure() will fix dimensions on next draw."""
    global viewport
    viewport = Viewport(level_px=33 * 16, sprite_size=16, level_size=33)
