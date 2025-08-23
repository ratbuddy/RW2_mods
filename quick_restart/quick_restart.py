# mods/quick_restart/quick_restart.py
# Quick Restart & Abandon mod for Rift Wizard 2 by ratbuddy
#
# License / Disclaimer:
#   This code is free to use, share, and modify however you like.
#   No permission needed, no credit required.
#   It comes with absolutely no warranty — use at your own risk.
#   If it breaks your game, your save, your computer, or your brain,
#   that’s on you :)
# ------------------------------------------------------------
# - Keyboard-only (no mouse targets), shown as hints at the bottom of Options
# - Quick Restart:
#     R          -> confirmation -> LOSS -> restart same mode (skip intro)
#     Shift + R  -> instant LOSS -> restart same mode (skip intro)
#     Mutated mode re-rolls new random mutators (trial_name == "MUTATED_RUN")
# - Abandon Run:
#     A          -> confirmation -> LOSS -> delete save & return to Title
#     Shift + A  -> instant LOSS -> delete save & return to Title
# - Logs to mods/quick_restart/quick_restart.log

import sys, os, pygame

LOG_PATH = os.path.join(os.path.dirname(__file__), "quick_restart.log")
def _log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

_log("quick_restart: importing")

# Grab the running game module (or import for source runs)
game = sys.modules.get("__main__")
if game is None:
    import RiftWizard2 as game
    _log("quick_restart: imported RiftWizard2")

import SteamAdapter
import Mutators  # needed to re-roll for Mutated mode

PyGameView = getattr(game, "PyGameView", None)
if PyGameView is None:
    _log("quick_restart: ERROR: PyGameView not found")
    raise RuntimeError("PyGameView not found; game version mismatch?")

# ---------- shared helpers ----------

def _qr_record_loss(self):
    """Reset streak and increment losses (same as death/abandon)."""
    try:
        s = SteamAdapter.get_stat('s')
        l = SteamAdapter.get_stat('l')
        SteamAdapter.set_stat('s', 0)
        SteamAdapter.set_stat('l', l + 1)
        _log(f"loss recorded s {s}->0, l {l}->{l+1}")
    except Exception as e:
        _log(f"loss record failed: {e!r}")

def _qr_skip_intro_to_level(self):
    """Skip story panel and jump to level."""
    try:
        self.message = None
        if hasattr(self, "next_message"):
            self.next_message = None
        if hasattr(self, "center_message"):
            self.center_message = False
        self.state = getattr(game, "STATE_LEVEL", self.state)
        _log("skipped intro: set state to STATE_LEVEL")
    except Exception as e:
        _log(f"skip-intro block failed: {e!r}")

# ---------- quick restart flow ----------

def _qr_restart_with_same_params(self):
    """
    Restart immediately with same overall mode, but:
    - If current run is MUTATED (trial_name == "MUTATED_RUN"), re-roll mutators via Mutators.get_random_mutators().
    - Trials/Weekly/Custom/Normal: preserve identity.
    Then skip intro and jump to the level.
    """
    trial_name = getattr(self.game, "trial_name", None)
    mutators   = getattr(self.game, "mutators", None)
    seed       = getattr(self.game, "seed", None)

    # Determine mutators for restart
    if trial_name == "MUTATED_RUN":
        try:
            mutators_arg = Mutators.get_random_mutators()
            _log("mutators re-rolled for MUTATED_RUN")
        except Exception as e:
            _log(f"get_random_mutators() failed: {e!r}; falling back to previous mutators")
            mutators_arg = mutators
    else:
        mutators_arg = mutators

    # Wipe current save and start new run
    try:
        game.abort_game()
        _log("abort_game() ok")
    except Exception as e:
        _log(f"abort_game() failed: {e!r}")

    try:
        self.play_sound("menu_confirm")
    except Exception:
        pass

    try:
        self.new_game(mutators=mutators_arg, trial_name=trial_name, seed=seed)
        _log(
            "new_game("
            f"mutators={'re-rolled' if trial_name=='MUTATED_RUN' else ('y' if mutators else 'n')}, "
            f"trial={trial_name}, seed={seed})"
        )
    except Exception as e:
        _log(f"new_game() failed: {e!r}")
        return

    _qr_skip_intro_to_level(self)

def _qr_open_restart_prompt(self):
    self.play_sound("menu_confirm")
    self.state = game.STATE_CONFIRM
    self.confirm_text = "Quick restart this run with the same mode?"
    self.confirm_yes = self._qr_confirm_restart
    self.confirm_no  = self._qr_abort_to_options
    self.examine_target = False
    _log("prompt opened: restart")

def _qr_confirm_restart(self):
    _qr_record_loss(self)
    _qr_restart_with_same_params(self)

# ---------- abandon flow ----------

def _qr_abandon_to_title(self):
    """
    Delete the save and return to title (main menu). Counts as a loss.
    """
    _qr_record_loss(self)
    try:
        game.abort_game()  # delete save & go to title flow
        _log("abort_game() ok (abandon)")
    except Exception as e:
        _log(f"abort_game() failed (abandon): {e!r}")

    try:
        self.play_sound("menu_confirm")
    except Exception:
        pass

    # Ensure we're at title
    try:
        self.state = getattr(game, "STATE_TITLE", self.state)
        _log("abandon: set state to STATE_TITLE")
    except Exception as e:
        _log(f"abandon: set title failed: {e!r}")

def _qr_open_abandon_prompt(self):
    self.play_sound("menu_confirm")
    self.state = game.STATE_CONFIRM
    self.confirm_text = "Abandon this run and return to Title?"
    self.confirm_yes = self._qr_confirm_abandon
    self.confirm_no  = self._qr_abort_to_options
    self.examine_target = False
    _log("prompt opened: abandon")

def _qr_confirm_abandon(self):
    _qr_abandon_to_title(self)

# ---------- shared confirm "no" ----------

def _qr_abort_to_options(self):
    self.play_sound("menu_confirm")
    self.state = game.STATE_OPTIONS
    _log("confirm aborted -> options")

# Attach helpers to class
setattr(PyGameView, "_qr_open_restart_prompt", _qr_open_restart_prompt)
setattr(PyGameView, "_qr_confirm_restart", _qr_confirm_restart)
setattr(PyGameView, "_qr_open_abandon_prompt", _qr_open_abandon_prompt)
setattr(PyGameView, "_qr_confirm_abandon", _qr_confirm_abandon)
setattr(PyGameView, "_qr_abort_to_options", _qr_abort_to_options)

# ---------- wrappers ----------

_orig_draw_options_menu = PyGameView.draw_options_menu
_orig_process_options_input = PyGameView.process_options_input

def _qr_draw_options_menu(self):
    _orig_draw_options_menu(self)
    # Add two non-interactive hint lines at the bottom of Options
    if getattr(self, "game", None) and self.state == game.STATE_OPTIONS:
        try:
            base_y = self.screen.get_height() - self.linesize * 3
            x = self.screen.get_width() // 2 - 320
            self.draw_string(
                "Quick Restart: R = confirm, Shift+R = instant (Mutated re-rolls)",
                self.screen, x, base_y, content_width=640
            )
            self.draw_string(
                "Abandon Run:  A = confirm, Shift+A = instant (deletes run, returns to Title)",
                self.screen, x, base_y + self.linesize, content_width=640
            )
        except Exception as e:
            _log(f"draw hints failed: {e!r}")

def _qr_process_options_input(self):
    if self.state == game.STATE_OPTIONS:
        # Handle R / Shift+R (Quick Restart)
        for evt in [e for e in self.events if e.type == pygame.KEYDOWN]:
            if evt.key == pygame.K_r:
                if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    _log("Shift+R -> instant restart")
                    _qr_record_loss(self)
                    _qr_restart_with_same_params(self)
                else:
                    _log("R -> prompt (restart)")
                    self._qr_open_restart_prompt()
                return

        # Handle A / Shift+A (Abandon to Title)
        for evt in [e for e in self.events if e.type == pygame.KEYDOWN]:
            if evt.key == pygame.K_a:
                if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    _log("Shift+A -> instant abandon")
                    _qr_abandon_to_title(self)
                else:
                    _log("A -> prompt (abandon)")
                    self._qr_open_abandon_prompt()
                return

    _orig_process_options_input(self)

# Install wrappers
PyGameView.draw_options_menu    = _qr_draw_options_menu
PyGameView.process_options_input = _qr_process_options_input
_log("installed (restart & abandon hotkeys)")
