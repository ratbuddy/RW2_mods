# mods/quicksave/quicksave.py
# Quicksave / Quickload mod for Rift Wizard 2 by ratbuddy
#
# License / Disclaimer:
#   This code is free to use, share, and modify however you like.
#   No permission needed, no credit required.
#   It comes with absolutely no warranty — use at your own risk.
#   If it breaks your game, your save, your computer, or your brain,
#   that's on you :)
# ------------------------------------------------------------
# F5 = Quicksave  (only when it's your turn / you can act)
# F8 = Quickload  (anytime during gameplay, including after death)
#
# The quicksave file is stored in mods/quicksave/quicksave.dat
# Only one quicksave slot — each F5 overwrites the previous one.

import sys, os, pygame
import dill as pickle

LOG_PATH = os.path.join(os.path.dirname(__file__), "quicksave.log")
QUICKSAVE_PATH = os.path.join(os.path.dirname(__file__), "quicksave.dat")

# Visual feedback duration (frames)
_FLASH_DURATION = 45


def _log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


# Truncate log on each game launch so it doesn't grow forever
try:
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("")
except Exception:
    pass

_log("quicksave: importing")

# Grab the running game module (or import for source runs)
game_module = sys.modules.get("__main__")
if game_module is None:
    import RiftWizard2 as game_module

    _log("quicksave: imported RiftWizard2")

import Game as GameModule

PyGameView = getattr(game_module, "PyGameView", None)
if PyGameView is None:
    _log("quicksave: ERROR: PyGameView not found")
    raise RuntimeError("PyGameView not found; game version mismatch?")

STATE_LEVEL = getattr(game_module, "STATE_LEVEL")
LAST_LEVEL = getattr(game_module, "LAST_LEVEL", 25)

# ---- visual feedback state ----
# Stores remaining frames to show the flash message.
# Attached to each PyGameView instance via attribute.
_QS_FLASH_ATTR = "_qs_flash_frames"
_QS_FLASH_MSG_ATTR = "_qs_flash_msg"


def _set_flash(self, msg):
    setattr(self, _QS_FLASH_ATTR, _FLASH_DURATION)
    setattr(self, _QS_FLASH_MSG_ATTR, msg)


# ---- quicksave ----


def _qs_quicksave(self):
    if not self.game:
        _log("quicksave: no active game")
        return
    if getattr(self.game, "gameover", False) or getattr(self.game, "victory", False):
        _log("quicksave: game is over, skipping")
        return
    try:
        tmp_path = QUICKSAVE_PATH + ".tmp"
        self.game.save_game(tmp_path)
        if os.path.exists(QUICKSAVE_PATH):
            os.remove(QUICKSAVE_PATH)
        os.rename(tmp_path, QUICKSAVE_PATH)
        _set_flash(self, "Quicksaved!")
        try:
            self.play_sound("menu_confirm")
        except Exception:
            pass
        _log(
            "quicksave: saved ok (run %s, level %d)"
            % (
                getattr(self.game, "run_number", "?"),
                getattr(self.game, "level_num", -1),
            )
        )
    except Exception as e:
        _set_flash(self, "Quicksave failed!")
        _log("quicksave: FAILED: %r" % e)


# ---- quickload ----


def _qs_quickload(self):
    if not os.path.exists(QUICKSAVE_PATH):
        _set_flash(self, "No quicksave found")
        _log("quickload: no quicksave file")
        return
    try:
        with open(QUICKSAVE_PATH, "rb") as f:
            game_obj = pickle.load(f)

        if getattr(game_obj, "build_compat_num", 0) != GameModule.BUILD_NUM:
            _set_flash(self, "Quicksave incompatible!")
            _log("quickload: incompatible build_compat_num")
            return

        # on_loaded expects a path like saves/<run>/game.dat to set logdir and run_number
        run_num = getattr(game_obj, "run_number", 0)
        proper_path = os.path.join("saves", str(run_num), "game.dat")
        game_obj.on_loaded(proper_path)

        # Reset UI state
        self.game = game_obj
        self.effects = []
        self.effect_queue = []
        self.cur_spell = None
        self.examine_target = None
        self.path = []
        self.gameover_frames = 0
        self.gameover_tiles = None
        self.deploy_target = None
        self.deploy_anim_frames = 0
        self.cast_fail_frames = 0
        self.fast_forward = False
        self.state = STATE_LEVEL

        # Restart music
        if self.game.level_num != LAST_LEVEL:
            self.play_battle_music()
        else:
            self.play_music("boss_theme")

        _set_flash(self, "Quickloaded!")
        try:
            self.play_sound("menu_confirm")
        except Exception:
            pass
        _log(
            "quickload: loaded ok (run %s, level %d)"
            % (run_num, getattr(game_obj, "level_num", -1))
        )
    except Exception as e:
        _set_flash(self, "Quickload failed!")
        _log("quickload: FAILED: %r" % e)


# ---- hook: process_level_input ----
# Intercepts F5/F8 before the normal gameplay input handler.
# F8 must be checked FIRST — before the gameover→reminisce redirect that
# normally swallows all keypresses once gameover_frames > 8.

_orig_process_level_input = PyGameView.process_level_input


def _qs_process_level_input(self):
    for evt in [e for e in self.events if e.type == pygame.KEYDOWN]:
        if evt.key == pygame.K_F5:
            if self.can_execute_inputs():
                _qs_quicksave(self)
                return
            break  # Don't swallow other input
        if evt.key == pygame.K_F8:
            _qs_quickload(self)
            return
    _orig_process_level_input(self)


PyGameView.process_level_input = _qs_process_level_input


# ---- hook: process_reminisce_input ----
# The "replay your run" screen after the gameover fade-out.

_orig_process_reminisce_input = PyGameView.process_reminisce_input


def _qs_process_reminisce_input(self):
    for evt in [e for e in self.events if e.type == pygame.KEYDOWN]:
        if evt.key == pygame.K_F8:
            _qs_quickload(self)
            return
    _orig_process_reminisce_input(self)


PyGameView.process_reminisce_input = _qs_process_reminisce_input


# ---- hook: draw_screen (visual feedback overlay) ----
# draw_screen is called every frame as the final blit, so the flash works
# during normal gameplay, gameover fade-out, and reminisce equally.

_orig_draw_screen = PyGameView.draw_screen


def _qs_draw_screen(self, color=None):
    # Draw flash text onto self.screen BEFORE the original draw_screen,
    # because draw_screen blits self.screen to the display and flips.
    frames = getattr(self, _QS_FLASH_ATTR, 0)
    if frames > 0:
        setattr(self, _QS_FLASH_ATTR, frames - 1)
        msg = getattr(self, _QS_FLASH_MSG_ATTR, "")

        # Fade out in the last third
        alpha = 255
        fade_start = _FLASH_DURATION // 3
        if frames < fade_start:
            alpha = int(255 * frames / fade_start)

        try:
            font = getattr(self, "font", None) or pygame.font.Font(None, 24)
            text_surf = font.render(msg, True, (255, 255, 100))
            text_surf.set_alpha(alpha)
            x = self.screen.get_width() // 2 - text_surf.get_width() // 2
            y = 8
            self.screen.blit(text_surf, (x, y))
        except Exception:
            pass

    _orig_draw_screen(self, color=color)


PyGameView.draw_screen = _qs_draw_screen


# ---- hook: new_game ----
# Invalidate quicksave when starting a fresh run so a stale quicksave
# from a previous run can't accidentally pollute the new one.

_orig_new_game = PyGameView.new_game


def _qs_new_game(self, *args, **kwargs):
    if os.path.exists(QUICKSAVE_PATH):
        try:
            os.remove(QUICKSAVE_PATH)
            _log("new_game: deleted stale quicksave")
        except Exception as e:
            _log("new_game: failed to delete quicksave: %r" % e)
    return _orig_new_game(self, *args, **kwargs)


PyGameView.new_game = _qs_new_game


# ---- hook: process_title_input ----
# Allow F8 quickload from the main menu (e.g. after dying and returning to title).

_orig_process_title_input = PyGameView.process_title_input


def _qs_process_title_input(self):
    for evt in [e for e in self.events if e.type == pygame.KEYDOWN]:
        if evt.key == pygame.K_F8:
            _qs_quickload(self)
            return
    _orig_process_title_input(self)


PyGameView.process_title_input = _qs_process_title_input

_log(
    "quicksave: installed (F5=quicksave, F8=quickload, works during gameover/reminisce)"
)
