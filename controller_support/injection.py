"""
Controller Support — Event injection: polls the controller and pushes
synthetic pygame events into the view's event list.

Two entry points:
  inject_controller_events()          — for states using the key_binds system
  inject_controller_events_hardcoded() — for states using raw pygame keys

Stick layout:
  Left stick / D-pad → movement AND spell targeting (the game auto-switches)
  Right stick        → reserved for viewport camera scroll (steam_deck_support mod)
"""

import time
import pygame

from .log import _log
from .config import (
    XboxButtons,
    MOVE_REPEAT_DELAY,
    MOVE_REPEAT_INTERVAL,
)
from .game_module import (
    KEY_BIND_CONFIRM,
    KEY_BIND_ABORT,
    KEY_BIND_PASS,
    KEY_BIND_CHAR,
    KEY_BIND_HELP,
    KEY_BIND_TAB,
    KEY_BIND_AUTOPICKUP,
    KEY_BIND_THREAT,
    KEY_BIND_INTERACT,
    KEY_BIND_REROLL,
    KEY_BIND_NEXT_EXAMINE_TARGET,
    KEY_BIND_PREV_EXAMINE_TARGET,
    STATE_LEVEL,
    STATE_TITLE,
    STATE_OPTIONS,
)
from .helpers import make_key_event, direction_to_key_bind, get_key_for_bind
from .repeater import DirectionRepeater
from .browse import (
    is_browsing,
    browse_open,
    browse_cycle,
    browse_confirm,
    browse_cancel,
    clear_browse,
)
from .walk_target import (
    is_walk_target_active,
    walk_target_enter,
    walk_target_update,
    walk_target_exit,
)

# ---------------------------------------------------------------------------
#  Repeater instances (module-level singletons)
# ---------------------------------------------------------------------------
left_repeater = DirectionRepeater(MOVE_REPEAT_DELAY, MOVE_REPEAT_INTERVAL)
browse_repeater = DirectionRepeater(MOVE_REPEAT_DELAY, MOVE_REPEAT_INTERVAL)

# The global ControllerState is set at init time via set_ctrl().
_ctrl = None


def set_ctrl(ctrl):
    """Called once at startup to hand in the shared ControllerState instance."""
    global _ctrl
    _ctrl = ctrl


# ---------------------------------------------------------------------------
#  Hardcoded direction keys (used by pick_mode, pick_trial, etc.)
# ---------------------------------------------------------------------------
_HARDCODED_DIR_KEYS = {
    (0, -1): pygame.K_UP,
    (0, 1): pygame.K_DOWN,
    (-1, 0): pygame.K_LEFT,
    (1, 0): pygame.K_RIGHT,
    (1, -1): pygame.K_KP9,
    (-1, -1): pygame.K_KP7,
    (1, 1): pygame.K_KP3,
    (-1, 1): pygame.K_KP1,
}


# ============================================================================
#  Main injection (key-bind states)
# ============================================================================


def inject_controller_events(view):
    """Poll the controller and inject synthetic key events for key-bind states."""
    frameno = getattr(view, "frameno", 0)

    # Deduplicate — only run once per frame
    if getattr(view, "_ctrl_injected_frame", -1) == frameno:
        return
    view._ctrl_injected_frame = frameno

    if not _ctrl.connected:
        _ctrl.try_init()
        if not _ctrl.connected:
            return

    try:
        _ctrl.poll(frameno)
    except Exception as e:
        _log(f"inject: poll exception: {e}")
        _ctrl._handle_disconnect()
        return

    state = view.state
    injected = []

    # Auto-cancel browse if we left level or spell got cleared
    if is_browsing():
        if state != STATE_LEVEL:
            clear_browse()
        elif not (hasattr(view, "cur_spell") and view.cur_spell):
            clear_browse()

    # Auto-cancel walk-target if we left level state
    if is_walk_target_active():
        if state != STATE_LEVEL:
            walk_target_exit(view, do_walk=False)

    # ---- WALK-TARGET MODE ----
    if is_walk_target_active():
        # A released → attempt to walk, then exit
        if not _ctrl.button_held(XboxButtons.A):
            walk_target_exit(view, do_walk=True)
            return

        # B pressed → cancel without walking
        if _ctrl.button_just_pressed(XboxButtons.B):
            walk_target_exit(view, do_walk=False)
            return

        # Update cursor from stick direction
        walk_target_update(view, _ctrl)
        return  # consume all input while in walk-target mode

    # ---- BROWSE MODE ----
    if is_browsing() and state == STATE_LEVEL:
        if _ctrl.button_just_pressed(XboxButtons.A):
            browse_confirm(view)
            return
        if _ctrl.button_just_pressed(XboxButtons.B):
            browse_cancel(view)
            return
        if _ctrl.button_just_pressed(XboxButtons.RB):
            from .browse import _browse_mode

            if _browse_mode == "spells":
                browse_cancel(view)
                return
        if _ctrl.button_just_pressed(XboxButtons.LB):
            from .browse import _browse_mode

            if _browse_mode == "items":
                browse_cancel(view)
                return

        # D-pad / left stick cycles the list
        for d in browse_repeater.update(_ctrl.get_combined_direction()):
            dx, dy = d
            if dy < 0:
                browse_cycle(view, -1)
            elif dy > 0:
                browse_cycle(view, 1)

        return  # consume all input while browsing

    # ---- BUTTON PRESSES ----

    if _ctrl.button_just_pressed(XboxButtons.A):
        # In STATE_LEVEL with no spell/deploy active → enter walk-target mode
        if (
            state == STATE_LEVEL
            and view.game
            and not (hasattr(view, "cur_spell") and view.cur_spell)
            and not (hasattr(view, "deploy_target") and view.deploy_target)
            and hasattr(view, "can_execute_inputs")
            and view.can_execute_inputs()
            and hasattr(view.game, "p1")
            and view.game.p1
        ):
            walk_target_enter(view)
            return  # skip remaining processing this frame
        else:
            key = get_key_for_bind(view, KEY_BIND_CONFIRM)
            if key:
                injected.append(make_key_event(key))

    if _ctrl.button_just_pressed(XboxButtons.B):
        key = get_key_for_bind(view, KEY_BIND_ABORT)
        if key:
            injected.append(make_key_event(key))

    if _ctrl.button_just_pressed(XboxButtons.X):
        key = get_key_for_bind(view, KEY_BIND_PASS)
        if key:
            injected.append(make_key_event(key))

    if _ctrl.button_just_pressed(XboxButtons.Y):
        key = get_key_for_bind(view, KEY_BIND_CHAR)
        if key:
            injected.append(make_key_event(key))

    if _ctrl.button_just_pressed(XboxButtons.START):
        key = get_key_for_bind(view, KEY_BIND_ABORT)
        if key:
            injected.append(make_key_event(key))

    if _ctrl.button_just_pressed(XboxButtons.BACK):
        key = get_key_for_bind(view, KEY_BIND_HELP)
        if key:
            injected.append(make_key_event(key))

    # RB — spell browser or tab-target
    if _ctrl.button_just_pressed(XboxButtons.RB):
        if state == STATE_LEVEL and view.game:
            if hasattr(view, "cur_spell") and view.cur_spell:
                key = get_key_for_bind(view, KEY_BIND_TAB)
                if key:
                    injected.append(make_key_event(key))
            elif not (hasattr(view, "deploy_target") and view.deploy_target):
                browse_open(view, "spells")
                return
        else:
            key = get_key_for_bind(view, KEY_BIND_NEXT_EXAMINE_TARGET)
            if key:
                injected.append(make_key_event(key))

    # LB — item browser or prev examine target
    if _ctrl.button_just_pressed(XboxButtons.LB):
        if state == STATE_LEVEL and view.game:
            if not (hasattr(view, "cur_spell") and view.cur_spell) and not (
                hasattr(view, "deploy_target") and view.deploy_target
            ):
                browse_open(view, "items")
                return
            else:
                key = get_key_for_bind(view, KEY_BIND_PREV_EXAMINE_TARGET)
                if key:
                    injected.append(make_key_event(key))
        else:
            key = get_key_for_bind(view, KEY_BIND_PREV_EXAMINE_TARGET)
            if key:
                injected.append(make_key_event(key))

    # Stick clicks
    if _ctrl.button_just_pressed(XboxButtons.L_STICK):
        if state == STATE_LEVEL and view.game:
            key = get_key_for_bind(view, KEY_BIND_AUTOPICKUP)
            if key:
                injected.append(make_key_event(key))

    if _ctrl.button_just_pressed(XboxButtons.R_STICK):
        key = get_key_for_bind(view, KEY_BIND_THREAT)
        if key:
            injected.append(make_key_event(key))

    # Triggers
    if _ctrl.rt_just_pressed():
        if state == STATE_LEVEL and view.game:
            if hasattr(view, "cur_spell") and view.cur_spell:
                key = get_key_for_bind(view, KEY_BIND_CONFIRM)
            else:
                key = get_key_for_bind(view, KEY_BIND_INTERACT)
            if key:
                injected.append(make_key_event(key))

    if _ctrl.lt_just_pressed():
        if state == STATE_LEVEL and view.game:
            key = get_key_for_bind(view, KEY_BIND_REROLL)
            if key:
                injected.append(make_key_event(key))

    # ---- DIRECTIONAL INPUT ----

    combined_dir = _ctrl.get_combined_direction()

    # Left stick / D-pad → movement keys.
    # When a spell is active, the game itself redirects movement keys to move
    # the targeting cursor instead of the player, so we always inject normal
    # direction key events here.
    #
    # Right stick is intentionally NOT used for targeting — it is reserved
    # for viewport camera scrolling (steam_deck_support mod).  The left stick
    # handles both movement AND spell targeting (the game switches
    # automatically when a spell is selected).
    for d in left_repeater.update(combined_dir):
        bind = direction_to_key_bind(*d)
        if bind is not None:
            key = get_key_for_bind(view, bind)
            if key:
                injected.append(make_key_event(key))

    # ---- INJECT ----
    if injected:
        view.events.extend(injected)


# ============================================================================
#  Hardcoded-key injection (pick mode, trial, setup, etc.)
# ============================================================================


def inject_controller_events_hardcoded(view):
    """Inject raw pygame key events for states that don't use key_binds."""
    frameno = getattr(view, "frameno", 0)

    if getattr(view, "_ctrl_injected_frame", -1) == frameno:
        return
    view._ctrl_injected_frame = frameno

    if not _ctrl.connected:
        _ctrl.try_init()
        if not _ctrl.connected:
            return

    try:
        _ctrl.poll(frameno)
    except Exception as e:
        _log(f"inject_hardcoded: poll exception: {e}")
        _ctrl._handle_disconnect()
        return

    injected = []

    if _ctrl.button_just_pressed(XboxButtons.A):
        injected.append(make_key_event(pygame.K_RETURN))
    if _ctrl.button_just_pressed(XboxButtons.B):
        injected.append(make_key_event(pygame.K_ESCAPE))
    if _ctrl.button_just_pressed(XboxButtons.X):
        injected.append(make_key_event(pygame.K_SPACE))

    for d in left_repeater.update(_ctrl.get_combined_direction()):
        hk = _HARDCODED_DIR_KEYS.get(d)
        if hk:
            injected.append(make_key_event(hk))

    if injected:
        view.events.extend(injected)
