"""
Controller Support — DirectionRepeater: initial-press + auto-repeat with debounce.
"""

import time

from .config import DEBOUNCE_TIME


class DirectionRepeater:
    """Handles initial delay + repeat for a directional input, with debounce.

    Debounce prevents double-inputs caused by:
    - Stick bouncing through neutral for 1–2 frames on a quick tap
    - Jitter between adjacent directions (e.g. right ↔ down-right)
    """

    def __init__(self, initial_delay, repeat_interval):
        self.initial_delay = initial_delay
        self.repeat_interval = repeat_interval
        self.active_dir = None
        self.next_fire_time = 0
        self.fired_initial = False
        self.last_fire_time = 0
        self.release_time = 0

    def update(self, direction):
        """Feed the current direction each frame. Returns a list of dirs to act on."""
        events = []
        now = time.time()

        if direction is None or direction == (0, 0):
            if self.active_dir is not None:
                self.release_time = now
            self.active_dir = None
            self.fired_initial = False
            return events

        # Debounce: don't fire again too soon after the previous event
        if now - self.last_fire_time < DEBOUNCE_TIME:
            return events

        if direction != self.active_dir:
            # Suppress bounce-back through neutral within debounce window
            if self.release_time > 0 and (now - self.release_time) < DEBOUNCE_TIME:
                self.active_dir = direction
                self.fired_initial = True
                self.next_fire_time = now + self.initial_delay
                return events

            # Genuine new direction
            self.active_dir = direction
            self.fired_initial = True
            self.next_fire_time = now + self.initial_delay
            self.last_fire_time = now
            events.append(direction)
        elif now >= self.next_fire_time:
            # Repeat
            self.next_fire_time = now + self.repeat_interval
            self.last_fire_time = now
            events.append(direction)

        return events
