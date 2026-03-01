"""
Controller Support — Spell / Item browse mode.

Lets the player press RB/LB to open a browser overlay, cycle through
spells or items with D-pad, preview targeting range, then confirm with A.
"""

from .log import _log
from .helpers import make_key_event, get_key_for_bind
from .game_module import KEY_BIND_CONFIRM


# ---------------------------------------------------------------------------
#  Module-level state
# ---------------------------------------------------------------------------
_browse_mode = None    # None | 'spells' | 'items'
_browse_index = 0      # Current index in the active list


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _get_browse_list(view):
    """Return the list being browsed (spells or items), or []."""
    if not view.game or not hasattr(view.game, 'p1'):
        return []
    if _browse_mode == 'spells':
        return view.game.p1.spells
    elif _browse_mode == 'items':
        return view.game.p1.items
    return []


def _browse_select_current(view):
    """Call choose_spell on the currently browsed entry."""
    lst = _get_browse_list(view)
    if not lst:
        return
    global _browse_index
    _browse_index = max(0, min(_browse_index, len(lst) - 1))
    entry = lst[_browse_index]
    if _browse_mode == 'items':
        view.choose_spell(entry.spell)
    else:
        view.choose_spell(entry)


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------

def is_browsing():
    """True if spell/item browse mode is active."""
    return _browse_mode is not None


def browse_open(view, mode):
    """Enter browse mode for 'spells' or 'items'."""
    global _browse_mode, _browse_index
    if not view.game or not hasattr(view.game, 'p1'):
        return
    lst = view.game.p1.spells if mode == 'spells' else view.game.p1.items
    if not lst:
        if hasattr(view, 'play_sound'):
            view.play_sound('menu_abort')
        return
    _browse_mode = mode
    _browse_index = 0
    _log(f"browse_open({mode}): {len(lst)} entries")
    _browse_select_current(view)


def browse_cycle(view, delta):
    """Move the browse index by *delta* (+1 / -1) and preview the selection."""
    global _browse_index
    lst = _get_browse_list(view)
    if not lst:
        return
    _browse_index = (_browse_index + delta) % len(lst)
    _browse_select_current(view)


def browse_confirm(view):
    """Confirm the current selection and inject a CONFIRM key so it casts immediately."""
    global _browse_mode
    _log(f"browse_confirm: {_browse_mode} index {_browse_index}")
    _browse_mode = None
    key = get_key_for_bind(view, KEY_BIND_CONFIRM)
    if key:
        view.events.append(make_key_event(key))


def browse_cancel(view):
    """Cancel browse mode and abort the previewed spell."""
    global _browse_mode
    _log(f"browse_cancel: {_browse_mode}")
    _browse_mode = None
    if hasattr(view, 'cur_spell') and view.cur_spell:
        view.abort_cur_spell()


def clear_browse():
    """Silently reset browse state (used when leaving level state)."""
    global _browse_mode
    _browse_mode = None
