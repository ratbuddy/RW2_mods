"""
Controller Support — ControllerState: polling, axis auto-detection, edge detection.

Handles joystick initialization, auto-detects axis mapping (sticks vs triggers)
by reading rest values, and provides per-frame state with edge detection for
buttons, triggers, sticks, and d-pad.
"""

import time
import pygame
import traceback

from .log import _log
from .config import (
    XboxHats, STICK_DEADZONE, DIRECTION_THRESHOLD, TRIGGER_THRESHOLD,
)

# How often (seconds) to re-scan for newly connected controllers.
_RESCAN_INTERVAL = 2.0


class ControllerState:
    """Tracks controller state between frames for edge detection & repeats.

    Axis mapping is auto-detected at connection time by reading rest values:
    - Triggers rest at -1.0 (SDL2/XInput convention)
    - Sticks rest near 0.0
    The first two stick-axes become left stick, the next two become right stick.
    """

    def __init__(self):
        self.joystick = None
        self.connected = False

        # Auto-detected axis indices (set in try_init)
        self.axis_left_x = 0
        self.axis_left_y = 1
        self.axis_right_x = -1   # -1 = not found
        self.axis_right_y = -1
        self.axis_lt = -1
        self.axis_rt = -1
        self.trigger_is_minus_one_rest = True

        # Frame deduplication
        self._last_poll_frame = -1

        # Button edge detection
        self.prev_buttons = {}
        self.curr_buttons = {}

        # Trigger states
        self.prev_lt = False
        self.prev_rt = False
        self.curr_lt = False
        self.curr_rt = False

        # D-pad previous state
        self.prev_hat = (0, 0)
        self.curr_hat = (0, 0)

        # Track stick directions as digital
        self.prev_left_dir = (0, 0)
        self.curr_left_dir = (0, 0)
        self.prev_right_dir = (0, 0)
        self.curr_right_dir = (0, 0)

        # Hot-plug: throttle re-scan attempts
        self._last_scan_time = 0.0

    # ------------------------------------------------------------------
    #  Init / auto-detect
    # ------------------------------------------------------------------

    def try_init(self):
        """Try to find and initialize a joystick. Auto-detects axis mapping.

        In pygame 1.x, joystick.init() on an already-initialized subsystem
        does NOT re-enumerate devices.  We must quit + re-init to detect
        controllers that were powered on after the game started.
        Re-scans are throttled to once every few seconds to avoid overhead.
        """
        if self.connected and self.joystick:
            return True

        # Throttle: don't re-scan every frame
        now = time.time()
        if now - self._last_scan_time < _RESCAN_INTERVAL:
            return False
        self._last_scan_time = now

        # Force full re-enumeration
        pygame.joystick.quit()
        pygame.joystick.init()
        count = pygame.joystick.get_count()
        if count == 0:
            self.connected = False
            return False

        try:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            self.connected = True
            name = self.joystick.get_name()
            n_buttons = self.joystick.get_numbuttons()
            n_axes = self.joystick.get_numaxes()
            n_hats = self.joystick.get_numhats()
            print(f"[Controller Support] Connected: {name}")
            print(f"[Controller Support]   Buttons: {n_buttons}, Axes: {n_axes}, Hats: {n_hats}")
            _log(f"CONNECTED: {name} | Buttons: {n_buttons}, Axes: {n_axes}, Hats: {n_hats}")

            self._auto_detect_axes(n_axes)
            return True
        except Exception as e:
            print(f"[Controller Support] Failed to init joystick: {e}")
            _log(f"FAILED to init joystick: {e}\n{traceback.format_exc()}")
            self.connected = False
            return False

    def _auto_detect_axes(self, n_axes):
        """Classify axes by rest value and assign stick / trigger indices."""
        stick_axes = []
        trigger_axes = []
        for i in range(n_axes):
            val = self.joystick.get_axis(i)
            if val < -0.8:
                trigger_axes.append(i)
            elif abs(val) < 0.5:
                stick_axes.append(i)

        _log(f"  Stick axes (rest ~0): {stick_axes}")
        _log(f"  Trigger axes (rest ~-1): {trigger_axes}")

        if len(stick_axes) >= 2:
            self.axis_left_x = stick_axes[0]
            self.axis_left_y = stick_axes[1]
        if len(stick_axes) >= 4:
            self.axis_right_x = stick_axes[2]
            self.axis_right_y = stick_axes[3]
        elif len(stick_axes) == 3:
            self.axis_right_x = stick_axes[2]
            _log("  WARNING: Only 3 stick axes detected; right stick Y unavailable")

        if len(trigger_axes) >= 1:
            self.axis_lt = trigger_axes[0]
            self.trigger_is_minus_one_rest = True
        if len(trigger_axes) >= 2:
            self.axis_rt = trigger_axes[1]
        if not trigger_axes:
            self.trigger_is_minus_one_rest = False
            _log("  No trigger axes detected; LT/RT may not work")

        _log(f"  Mapping: LStick({self.axis_left_x},{self.axis_left_y}) "
             f"RStick({self.axis_right_x},{self.axis_right_y}) "
             f"LT({self.axis_lt}) RT({self.axis_rt})")
        print(f"[Controller Support]   Mapping: "
              f"LStick({self.axis_left_x},{self.axis_left_y}) "
              f"RStick({self.axis_right_x},{self.axis_right_y}) "
              f"LT({self.axis_lt}) RT({self.axis_rt})")

    # ------------------------------------------------------------------
    #  Per-frame polling
    # ------------------------------------------------------------------

    def poll(self, frameno=0):
        """Read current controller state. Call once per frame."""
        if not self.connected or not self.joystick:
            return

        # Deduplicate multiple calls in the same frame
        if self._last_poll_frame == frameno:
            return
        self._last_poll_frame = frameno

        # Detect mid-session disconnects
        try:
            pygame.joystick.init()  # no-op if already init'd
            if pygame.joystick.get_count() == 0:
                self._handle_disconnect()
                return
        except Exception:
            self._handle_disconnect()
            return

        num_axes = self.joystick.get_numaxes()

        # Buttons
        self.prev_buttons = dict(self.curr_buttons)
        self.curr_buttons = {
            i: self.joystick.get_button(i)
            for i in range(self.joystick.get_numbuttons())
        }

        # Triggers
        self.prev_lt = self.curr_lt
        self.prev_rt = self.curr_rt
        self.curr_lt = self._read_trigger(self.axis_lt, num_axes)
        self.curr_rt = self._read_trigger(self.axis_rt, num_axes)

        # D-pad
        self.prev_hat = self.curr_hat
        self.curr_hat = (
            self.joystick.get_hat(XboxHats.DPAD)
            if self.joystick.get_numhats() > 0
            else (0, 0)
        )

        # Sticks → digital
        self.prev_left_dir = self.curr_left_dir
        self.prev_right_dir = self.curr_right_dir
        self.curr_left_dir = self._read_stick(
            self.axis_left_x, self.axis_left_y, num_axes
        )
        self.curr_right_dir = self._read_stick(
            self.axis_right_x, self.axis_right_y, num_axes
        )

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------

    def _read_trigger(self, axis_idx, num_axes):
        """Return True if the given trigger axis exceeds the threshold."""
        if axis_idx < 0 or num_axes <= axis_idx:
            return False
        raw = self.joystick.get_axis(axis_idx)
        val = (raw + 1.0) / 2.0 if self.trigger_is_minus_one_rest else raw
        return val > TRIGGER_THRESHOLD

    def _read_stick(self, axis_x, axis_y, num_axes):
        """Read two axes and return a digital (dx, dy) direction."""
        if axis_x < 0 or axis_y < 0:
            return (0, 0)
        if num_axes <= max(axis_x, axis_y):
            return (0, 0)
        x = self.joystick.get_axis(axis_x)
        y = self.joystick.get_axis(axis_y)
        return self._stick_to_digital(x, y)

    @staticmethod
    def _stick_to_digital(x, y):
        """Convert analog stick to 8-way digital direction.

        Uses a radial deadzone (STICK_DEADZONE) to reject drift, then a
        lower per-axis threshold (DIRECTION_THRESHOLD) so diagonals are
        easier to hit.
        """
        magnitude = (x * x + y * y) ** 0.5
        if magnitude < STICK_DEADZONE:
            return (0, 0)

        dx = 0
        dy = 0
        if x > DIRECTION_THRESHOLD:
            dx = 1
        elif x < -DIRECTION_THRESHOLD:
            dx = -1
        if y > DIRECTION_THRESHOLD:
            dy = 1   # SDL Y axis: down is positive
        elif y < -DIRECTION_THRESHOLD:
            dy = -1
        return (dx, dy)

    # ------------------------------------------------------------------
    #  Edge-detection queries
    # ------------------------------------------------------------------

    def button_just_pressed(self, btn):
        """True on the single frame a button transitions from released → pressed."""
        return self.curr_buttons.get(btn, False) and not self.prev_buttons.get(btn, False)

    def button_held(self, btn):
        """True while a button is held down."""
        return self.curr_buttons.get(btn, False)

    def button_just_released(self, btn):
        """True on the single frame a button transitions from pressed → released."""
        return not self.curr_buttons.get(btn, False) and self.prev_buttons.get(btn, False)

    def lt_just_pressed(self):
        return self.curr_lt and not self.prev_lt

    def rt_just_pressed(self):
        return self.curr_rt and not self.prev_rt

    def get_dpad_direction(self):
        """Current d-pad as (dx, dy) in screen coords (down = +y)."""
        hx, hy = self.curr_hat
        return (hx, -hy)  # SDL hat: up = +1, we want up = -1

    def get_dpad_just_pressed(self):
        """D-pad direction if it just changed to a new non-zero value."""
        curr = self.get_dpad_direction()
        prev = (self.prev_hat[0], -self.prev_hat[1])
        if curr != (0, 0) and curr != prev:
            return curr
        return None

    def get_left_dir_just_pressed(self):
        """Left stick direction if it just entered or changed direction."""
        if self.curr_left_dir != (0, 0) and self.curr_left_dir != self.prev_left_dir:
            return self.curr_left_dir
        return None

    def get_right_dir_just_pressed(self):
        """Right stick direction if it just entered or changed direction."""
        if self.curr_right_dir != (0, 0) and self.curr_right_dir != self.prev_right_dir:
            return self.curr_right_dir
        return None

    def get_combined_direction(self):
        """Direction from left stick or d-pad (d-pad wins)."""
        dpad = self.get_dpad_direction()
        return dpad if dpad != (0, 0) else self.curr_left_dir

    def get_combined_dir_just_pressed(self):
        """Combined direction if just pressed (edge detection)."""
        dpad = self.get_dpad_just_pressed()
        return dpad if dpad else self.get_left_dir_just_pressed()

    # ------------------------------------------------------------------
    #  Disconnect handling
    # ------------------------------------------------------------------

    def _handle_disconnect(self):
        """Clean up after a controller is unplugged mid-session."""
        if self.connected:
            print("[Controller Support] Controller disconnected")
            _log("Controller disconnected mid-session")
        self.connected = False
        self.joystick = None
