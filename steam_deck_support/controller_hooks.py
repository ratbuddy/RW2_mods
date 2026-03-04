"""
Steam Deck Panels — Controller integration (RW2).

If the controller_support mod is loaded, this patches its injection layer
to add panel toggle and viewport shortcuts:
  Back + LB       → toggle left panel
  Back + RB       → toggle right panel
  Back + Y        → toggle both panels
  Back + D-pad Up → zoom in
  Back + D-pad Dn → zoom out
  Right stick     → scroll camera when expanded or zoomed (not targeting)

These combos are checked before the normal button handling, so they
take priority only while Back is held.

IMPORTANT: the controller_support mod's patches.py imports
inject_controller_events by name (from .injection import ...), so
replacing injection_mod.inject_controller_events alone does NOT work —
we must also patch the patches module's local reference.
"""

import sys
import time

from . import panel_state as ps
from .viewport import viewport as vp


def _needs_scroll():
    """True when the level is expanded (panels collapsed) or zoomed."""
    return vp.is_zoomed or ps.left_panel.frac < 0.999 or ps.right_panel.frac < 0.999


def try_integrate_controller():
    """Attempt to hook into the controller_support mod if it's loaded.
    Safe to call even if the controller mod is not present."""

    # Check if the controller_support mod is loaded
    ctrl_mod = sys.modules.get("mods.controller_support.controller_support")
    if ctrl_mod is None:
        print(
            "[Deck Panels] Controller support mod not detected, "
            "skipping controller integration"
        )
        return False

    # Get the controller state instance
    ctrl = getattr(ctrl_mod, "ctrl", None)
    if ctrl is None:
        print(
            "[Deck Panels] Could not find controller state, "
            "skipping controller integration"
        )
        return False

    # Get button constants
    try:
        from mods.controller_support.config import XboxButtons, STICK_DEADZONE
    except ImportError:
        print("[Deck Panels] Could not import controller config, skipping")
        return False

    # Get the injection module to wrap inject_controller_events
    try:
        import mods.controller_support.injection as injection_mod
    except ImportError:
        print("[Deck Panels] Could not import injection module, skipping")
        return False

    # Get the patches module — its local reference must also be updated
    try:
        import mods.controller_support.patches as patches_mod
    except ImportError:
        patches_mod = None

    _original_inject = injection_mod.inject_controller_events
    _last_scroll_time = [time.monotonic()]
    _last_panels_frame = [-1]  # frame-level dedup (multiple wrappers call us)

    # Import browse check for auto-slide panel
    from mods.controller_support.browse import is_browsing as _is_browsing

    def _inject_and_check_browse(view):
        """Run original inject and auto-show left panel if browse just opened."""
        was_browsing = _is_browsing()
        _original_inject(view)
        if not was_browsing and _is_browsing():
            ps.left_panel.show()

    def _inject_with_panels(view):
        """Wrapped injection that checks for panel toggle / viewport combos.

        Back is used as a modifier key for panel/zoom combos.  While Back
        is held we suppress the default Back→Help mapping so it doesn't
        fire on the first frame before the user can press LB/RB/Y.

        NOTE: this function is called multiple times per frame (once per
        wrapped process_*_input method), so we must deduplicate our own
        combo/scroll logic and only run it on the first call each frame.
        """
        if not ctrl.connected:
            return _inject_and_check_browse(view)

        frameno = getattr(view, "frameno", 0)

        # Poll once per frame
        try:
            ctrl.poll(frameno)
        except Exception:
            pass

        if not ctrl.connected:
            return _inject_and_check_browse(view)

        # --- Our own per-frame logic (run only on the first call) ---
        first_call = _last_panels_frame[0] != frameno
        if first_call:
            _last_panels_frame[0] = frameno

            back_held = ctrl.button_held(XboxButtons.BACK)

            # --- Back + button combos ---
            if back_held:
                if ctrl.button_just_pressed(XboxButtons.LB):
                    ps.toggle_left()
                    return
                if ctrl.button_just_pressed(XboxButtons.RB):
                    ps.toggle_right()
                    return
                if ctrl.button_just_pressed(XboxButtons.Y):
                    ps.toggle_both()
                    return

                # D-pad zoom while Back is held
                joy = ctrl.joystick
                if joy:
                    hat = joy.get_hat(0) if joy.get_numhats() > 0 else (0, 0)
                    if hat[1] == 1:   # D-pad up
                        vp.zoom_in()
                        return
                    elif hat[1] == -1:  # D-pad down
                        vp.zoom_out()
                        return

            # --- Right stick camera scroll when expanded or zoomed ---
            if _needs_scroll():
                cur_spell = getattr(view, "cur_spell", None)
                if cur_spell is None:
                    joy = ctrl.joystick
                    rx_axis = ctrl.axis_right_x
                    ry_axis = ctrl.axis_right_y
                    if joy and rx_axis >= 0 and ry_axis >= 0:
                        rx = joy.get_axis(rx_axis)
                        ry = joy.get_axis(ry_axis)
                        mag = (rx * rx + ry * ry) ** 0.5
                        if mag > STICK_DEADZONE:
                            now = time.monotonic()
                            dt = min(now - _last_scroll_time[0], 0.1)
                            _last_scroll_time[0] = now
                            vp.scroll(rx, ry, dt)

        # --- Suppress modifier buttons while Back is held ---
        # While Back is held as a modifier, suppress Back AND the combo
        # buttons (LB, RB, Y) so their normal actions (Help, crafting,
        # spell browse, character sheet) don't fire in the original inject.
        if ctrl.button_held(XboxButtons.BACK):
            suppress = [XboxButtons.BACK, XboxButtons.LB, XboxButtons.RB, XboxButtons.Y]
            saved = {btn: ctrl.prev_buttons.get(btn, False) for btn in suppress}
            for btn in suppress:
                ctrl.prev_buttons[btn] = True  # makes button_just_pressed → False
            try:
                return _inject_and_check_browse(view)
            finally:
                for btn in suppress:
                    ctrl.prev_buttons[btn] = saved[btn]

        # Fall through to normal injection
        return _inject_and_check_browse(view)

    # --- Replace the function everywhere it's referenced ---

    # 1. Module attribute (for any new callers)
    injection_mod.inject_controller_events = _inject_with_panels

    # 2. patches module's local binding (the actual call site!)
    #    patches.py does: from .injection import inject_controller_events
    #    so it has a local reference we must overwrite.
    if patches_mod is not None:
        patches_mod.inject_controller_events = _inject_with_panels

    print(
        "[Deck Panels] Controller integration active: "
        "Back+LB/RB/Y panels, Back+Dpad zoom, R-stick scroll"
    )
    return True
