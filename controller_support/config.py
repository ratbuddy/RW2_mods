"""
Controller Support — Configuration constants.

All tunable parameters (deadzones, thresholds, timing, button maps) live here
so they're easy to find and adjust without digging through logic code.
"""

# ============================================================================
#  BUTTON / HAT INDICES  (SDL2 / XInput mapping)
# ============================================================================

class XboxButtons:
    """Button indices for a standard Xbox controller."""
    A = 0
    B = 1
    X = 2
    Y = 3
    LB = 4
    RB = 5
    BACK = 6      # Select / Back / View
    START = 7
    L_STICK = 8
    R_STICK = 9


class XboxHats:
    DPAD = 0


# ============================================================================
#  ANALOG STICK
# ============================================================================

# Radial (circular) deadzone — stick magnitude must exceed this to register.
STICK_DEADZONE = 0.25

# Per-axis threshold for direction detection AFTER the radial deadzone passes.
# Lower than STICK_DEADZONE so diagonals register more easily.
# e.g. stick at (0.5, 0.18) → magnitude 0.53 passes, and both axes exceed
# 0.15, producing a diagonal instead of pure horizontal.
DIRECTION_THRESHOLD = 0.15


# ============================================================================
#  REPEAT / DEBOUNCE TIMING
# ============================================================================

# Right-stick cursor movement
CURSOR_REPEAT_DELAY = 0.30      # Seconds before first repeat
CURSOR_REPEAT_INTERVAL = 0.10   # Seconds between subsequent repeats

# Left-stick / D-pad movement and menu navigation
MOVE_REPEAT_DELAY = 0.22
MOVE_REPEAT_INTERVAL = 0.12

# Minimum gap (seconds) between any two direction events from the same repeater.
# Prevents double-inputs from stick bounce through neutral or direction jitter.
DEBOUNCE_TIME = 0.07


# ============================================================================
#  TRIGGERS
# ============================================================================

# Normalized trigger value (0.0–1.0) required to count as "pressed".
TRIGGER_THRESHOLD = 0.3
