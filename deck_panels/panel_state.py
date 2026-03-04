"""
Steam Deck Panels — Panel visibility state and animation.

Manages the collapsed/expanded/sliding state of left (character) and
right (examine) side panels.  Each panel has an independent visibility
float (0.0 = fully collapsed, 1.0 = fully expanded) that is lerped
every frame.
"""

import time

# ---------------------------------------------------------------------------
#  Configuration
# ---------------------------------------------------------------------------
SLIDE_DURATION = 0.18  # seconds for full slide
DEFAULT_LEFT_VISIBLE = True
DEFAULT_RIGHT_VISIBLE = True
# How much of the panel width to keep visible as a "tab" when collapsed
TAB_PX = 0  # 0 = fully hidden when collapsed


class PanelState:
    """Tracks visibility for one side panel."""

    __slots__ = ("visible", "_frac", "_last_time")

    def __init__(self, visible: bool = True):
        self.visible = visible
        self._frac = 1.0 if visible else 0.0
        self._last_time = time.monotonic()

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------
    def toggle(self):
        self.visible = not self.visible

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    @property
    def frac(self) -> float:
        """Current visibility fraction in [0, 1]. Updated by tick()."""
        return self._frac

    @property
    def is_fully_open(self) -> bool:
        return self._frac >= 1.0

    @property
    def is_fully_closed(self) -> bool:
        return self._frac <= 0.0

    @property
    def is_animating(self) -> bool:
        return 0.0 < self._frac < 1.0

    def tick(self):
        """Call once per frame to advance the slide animation."""
        now = time.monotonic()
        dt = now - self._last_time
        self._last_time = now

        target = 1.0 if self.visible else 0.0
        if self._frac == target:
            return

        step = dt / max(SLIDE_DURATION, 0.001)
        if target > self._frac:
            self._frac = min(self._frac + step, 1.0)
        else:
            self._frac = max(self._frac - step, 0.0)

    def effective_width(self, full_width: int) -> int:
        """How many pixels of the panel are currently visible."""
        return int(full_width * self._frac) + (TAB_PX if self._frac < 1.0 else 0)


# ---------------------------------------------------------------------------
#  Global instances
# ---------------------------------------------------------------------------
left_panel = PanelState(DEFAULT_LEFT_VISIBLE)
right_panel = PanelState(DEFAULT_RIGHT_VISIBLE)


def toggle_left():
    left_panel.toggle()


def toggle_right():
    right_panel.toggle()


def toggle_both():
    # If either is open, close both; otherwise open both
    if left_panel.visible or right_panel.visible:
        left_panel.hide()
        right_panel.hide()
    else:
        left_panel.show()
        right_panel.show()


def tick():
    """Advance both panels' animations. Call once per frame."""
    left_panel.tick()
    right_panel.tick()


def left_offset(full_width: int) -> int:
    """X-offset for blitting the left panel (negative = off-screen)."""
    ew = left_panel.effective_width(full_width)
    return ew - full_width  # ranges from -full_width to 0


def right_offset(screen_width: int, full_width: int) -> int:
    """X-position for blitting the right panel."""
    ew = right_panel.effective_width(full_width)
    return screen_width - ew  # ranges from screen_width to screen_width - full_width


def level_x_offset(full_margin: int) -> int:
    """X-position for the level display accounting for left panel state."""
    return full_margin + left_offset(full_margin)


def needs_redraw() -> bool:
    """True if any panel is mid-slide and needs continuous redraw."""
    return left_panel.is_animating or right_panel.is_animating
