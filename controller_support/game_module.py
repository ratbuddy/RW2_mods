"""
Controller Support — Game module access and shared constants.

Handles the critical import of the running game module (__main__) and
exports all KEY_BIND_* / STATE_* constants and PyGameView needed by
the rest of the mod.
"""

import sys

from .log import _log

# ---------------------------------------------------------------------------
#  Grab the live game module
# ---------------------------------------------------------------------------
# The main script runs as __main__; importing by filename would re-execute it.
_game = sys.modules.get("__main__")
if _game is None:
    _log("WARNING: __main__ not in sys.modules, falling back to import RiftWizard2")
    import RiftWizard2 as _game  # noqa: F401
else:
    _log("Using __main__ module (found in sys.modules)")

# Register __main__ as 'RiftWizard2' so dill.load() in save/load doesn't
# re-execute the game script.
if "RiftWizard2" not in sys.modules:
    sys.modules["RiftWizard2"] = _game
    _log("Registered __main__ as 'RiftWizard2' in sys.modules")

# ---------------------------------------------------------------------------
#  PyGameView
# ---------------------------------------------------------------------------
PyGameView = getattr(_game, "PyGameView", None)
if PyGameView is None:
    _log("ERROR: PyGameView not found in game module!")
    raise RuntimeError("PyGameView not found; game version mismatch?")

# ---------------------------------------------------------------------------
#  Point
# ---------------------------------------------------------------------------
try:
    from Level import Point  # noqa: F401
except ImportError:
    Point = getattr(_game, "Point", None)
    if Point is None:
        _log("ERROR: Could not import Point!")
        raise

# ---------------------------------------------------------------------------
#  Key-bind constants
# ---------------------------------------------------------------------------
KEY_BIND_UP                = _game.KEY_BIND_UP
KEY_BIND_DOWN              = _game.KEY_BIND_DOWN
KEY_BIND_LEFT              = _game.KEY_BIND_LEFT
KEY_BIND_RIGHT             = _game.KEY_BIND_RIGHT
KEY_BIND_UP_RIGHT          = _game.KEY_BIND_UP_RIGHT
KEY_BIND_UP_LEFT           = _game.KEY_BIND_UP_LEFT
KEY_BIND_DOWN_RIGHT        = _game.KEY_BIND_DOWN_RIGHT
KEY_BIND_DOWN_LEFT         = _game.KEY_BIND_DOWN_LEFT
KEY_BIND_PASS              = _game.KEY_BIND_PASS
KEY_BIND_CONFIRM           = _game.KEY_BIND_CONFIRM
KEY_BIND_ABORT             = _game.KEY_BIND_ABORT
KEY_BIND_SPELL_1           = _game.KEY_BIND_SPELL_1
KEY_BIND_SPELL_2           = _game.KEY_BIND_SPELL_2
KEY_BIND_SPELL_3           = _game.KEY_BIND_SPELL_3
KEY_BIND_SPELL_4           = _game.KEY_BIND_SPELL_4
KEY_BIND_SPELL_5           = _game.KEY_BIND_SPELL_5
KEY_BIND_SPELL_6           = _game.KEY_BIND_SPELL_6
KEY_BIND_SPELL_7           = _game.KEY_BIND_SPELL_7
KEY_BIND_SPELL_8           = _game.KEY_BIND_SPELL_8
KEY_BIND_SPELL_9           = _game.KEY_BIND_SPELL_9
KEY_BIND_SPELL_10          = _game.KEY_BIND_SPELL_10
KEY_BIND_MODIFIER_1        = _game.KEY_BIND_MODIFIER_1
KEY_BIND_MODIFIER_2        = _game.KEY_BIND_MODIFIER_2
KEY_BIND_TAB               = _game.KEY_BIND_TAB
KEY_BIND_VIEW              = _game.KEY_BIND_VIEW
KEY_BIND_WALK              = _game.KEY_BIND_WALK
KEY_BIND_AUTOPICKUP        = _game.KEY_BIND_AUTOPICKUP
KEY_BIND_CHAR              = _game.KEY_BIND_CHAR
KEY_BIND_SPELLS            = _game.KEY_BIND_SPELLS
KEY_BIND_SKILLS            = _game.KEY_BIND_SKILLS
KEY_BIND_HELP              = _game.KEY_BIND_HELP
KEY_BIND_INTERACT          = _game.KEY_BIND_INTERACT
KEY_BIND_MESSAGE_LOG       = _game.KEY_BIND_MESSAGE_LOG
KEY_BIND_THREAT            = _game.KEY_BIND_THREAT
KEY_BIND_LOS               = _game.KEY_BIND_LOS
KEY_BIND_NEXT_EXAMINE_TARGET = _game.KEY_BIND_NEXT_EXAMINE_TARGET
KEY_BIND_PREV_EXAMINE_TARGET = _game.KEY_BIND_PREV_EXAMINE_TARGET
KEY_BIND_FF                = _game.KEY_BIND_FF
KEY_BIND_REROLL            = _game.KEY_BIND_REROLL

# ---------------------------------------------------------------------------
#  State constants
# ---------------------------------------------------------------------------
STATE_LEVEL                = _game.STATE_LEVEL
STATE_CHAR_SHEET           = _game.STATE_CHAR_SHEET
STATE_SHOP                 = _game.STATE_SHOP
STATE_TITLE                = _game.STATE_TITLE
STATE_OPTIONS              = _game.STATE_OPTIONS
STATE_MESSAGE              = _game.STATE_MESSAGE
STATE_CONFIRM              = _game.STATE_CONFIRM
STATE_REMINISCE            = _game.STATE_REMINISCE
STATE_REBIND               = _game.STATE_REBIND
STATE_COMBAT_LOG           = _game.STATE_COMBAT_LOG
STATE_PICK_MODE            = _game.STATE_PICK_MODE
STATE_PICK_TRIAL           = _game.STATE_PICK_TRIAL
STATE_SETUP_CUSTOM         = _game.STATE_SETUP_CUSTOM
STATE_PICK_MUTATOR_PARAMS  = _game.STATE_PICK_MUTATOR_PARAMS
STATE_ENTER_MUTATOR_VALUE  = _game.STATE_ENTER_MUTATOR_VALUE
