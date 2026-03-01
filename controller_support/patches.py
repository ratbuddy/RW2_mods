"""
Controller Support — Monkey-patch wrappers applied to PyGameView methods.

Three wrapper types:
  _make_wrapper()          — for states driven by key_binds (most of the game)
  _wrap_hardcoded_state()  — for states using raw pygame keys
  _wrap_message_input()    — for message/dialog states (any-key-to-advance)
"""

import pygame

from .log import _log
from .config import XboxButtons
from .helpers import make_key_event
from .injection import inject_controller_events, inject_controller_events_hardcoded

# The global ControllerState — set by apply_patches().
_ctrl = None


# ============================================================================
#  Wrapper factories
# ============================================================================

def _make_wrapper(original_method):
    """Wrap a key-bind input method to inject controller events first."""
    def wrapper(self, *args, **kwargs):
        inject_controller_events(self)
        return original_method(self, *args, **kwargs)
    wrapper.__name__ = original_method.__name__
    wrapper.__qualname__ = original_method.__qualname__
    return wrapper


def _wrap_hardcoded_state(original_method):
    """Wrap a hardcoded-key input method to inject controller events first."""
    def wrapper(self, *args, **kwargs):
        inject_controller_events_hardcoded(self)
        return original_method(self, *args, **kwargs)
    wrapper.__name__ = original_method.__name__
    wrapper.__qualname__ = original_method.__qualname__
    return wrapper


def _wrap_message_input(original_method):
    """Wrap process_message_input — any button press → K_RETURN."""
    def wrapper(self, *args, **kwargs):
        frameno = getattr(self, 'frameno', 0)
        if getattr(self, '_ctrl_injected_frame', -1) != frameno:
            self._ctrl_injected_frame = frameno
            if not _ctrl.connected:
                _ctrl.try_init()
            if _ctrl.connected:
                try:
                    _ctrl.poll(frameno)
                except Exception:
                    _ctrl._handle_disconnect()
                if _ctrl.connected:
                    if (_ctrl.button_just_pressed(XboxButtons.A)
                            or _ctrl.button_just_pressed(XboxButtons.B)
                            or _ctrl.button_just_pressed(XboxButtons.X)):
                        self.events.append(make_key_event(pygame.K_RETURN))
        return original_method(self, *args, **kwargs)
    wrapper.__name__ = original_method.__name__
    wrapper.__qualname__ = original_method.__qualname__
    return wrapper


# ============================================================================
#  Patch application
# ============================================================================

# Methods driven by the key_binds system
_KEYBIND_METHODS = [
    'process_level_input',
    'process_shop_input',
    'process_char_sheet_input',
    'process_options_input',
    'process_confirm_input',
    'process_combat_log_input',
    'process_examine_panel_input',
    'process_title_input',
]

# Methods using hardcoded pygame keys
_HARDCODED_METHODS = [
    'process_pick_mode_input',
    'process_pick_trial_input',
    'process_setup_custom_input',
    'process_pick_mutator_params_input',
    'process_enter_mutator_value_input',
    'process_reminisce_input',
]


def apply_patches(PyGameView, ctrl):
    """Apply all monkey-patches to PyGameView and store the ctrl reference."""
    global _ctrl
    _ctrl = ctrl

    for name in _KEYBIND_METHODS:
        original = getattr(PyGameView, name, None)
        if original is None:
            _log(f"WARNING: {name} not found on PyGameView")
            continue
        setattr(PyGameView, name, _make_wrapper(original))

    for name in _HARDCODED_METHODS:
        original = getattr(PyGameView, name, None)
        if original is None:
            _log(f"WARNING: {name} not found on PyGameView")
            continue
        setattr(PyGameView, name, _wrap_hardcoded_state(original))

    # Message input (any button advances)
    original = getattr(PyGameView, 'process_message_input', None)
    if original:
        PyGameView.process_message_input = _wrap_message_input(original)

    total = len(_KEYBIND_METHODS) + len(_HARDCODED_METHODS) + 1
    _log(f"Patched {total} PyGameView methods")
    print(f"[Controller Support] Patched {total} input methods")
