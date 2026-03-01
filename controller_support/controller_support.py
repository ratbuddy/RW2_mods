"""
Controller Support Mod for Rift Wizard 2
=========================================
Adds Xbox/XInput gamepad support via pygame.joystick.

Button mapping (Xbox layout):
  Left Stick / D-pad : Move (level) / Navigate (menus)
  Right Stick        : Grid cursor for spell targeting
  A                  : Confirm / Cast / Interact
  B                  : Cancel / Abort / Back
  X                  : Pass Turn / Channel
  Y                  : Character Sheet
  RB                 : Open spell browser (D-pad to cycle, A to pick, B/RB to cancel)
  LB                 : Open item browser  (D-pad to cycle, A to pick, B/LB to cancel)
  RT                 : Interact (portals/shops) or Cast when spell active
  LT                 : Reroll rifts
  Start              : Options / Pause
  Back/Select        : Help
  Left Stick Click   : Autopickup
  Right Stick Click  : Toggle threat zone

This is the entry point loaded by the game's mod system.  All logic lives
in sibling modules — see config.py, controller_state.py, injection.py, etc.
"""

import pygame

from .log import _log
from .game_module import PyGameView            # also registers dill alias
from .controller_state import ControllerState
from .injection import set_ctrl
from .patches import apply_patches

_log("========================================")
_log("Controller Support mod: import start")
_log("========================================")

# ---------------------------------------------------------------------------
#  Create the global controller, wire it into the injection layer, and patch
# ---------------------------------------------------------------------------
ctrl = ControllerState()
set_ctrl(ctrl)                   # injection.py needs the instance
apply_patches(PyGameView, ctrl)  # patches.py needs both

# Attempt initial connection at load time
ctrl.try_init()

print("[Controller Support] Controller support mod loaded successfully!")
print("[Controller Support] Button layout: Xbox (A=Confirm, B=Cancel, X=Pass, Y=Char Sheet)")
print("[Controller Support] Spells: RB to browse, LB to browse items, D-pad to cycle, A to pick")
_log("Controller Support mod: import complete, all patches applied")
_log(f"  pygame version: {pygame.version.ver}")
_log(f"  controller connected at load time: {ctrl.connected}")
