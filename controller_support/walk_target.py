"""
Controller Support — Walk-target mode.

Hold A to enter a 1-tile targeting overlay that shows walkable adjacent tiles
using the game's red/green spell-targeting highlights.  Use the left stick to
select a tile, release A to walk there.
"""

from .game_module import Point
from .log import _log


# ---------------------------------------------------------------------------
#  Module state
# ---------------------------------------------------------------------------
_active = False
_step_spell = None


def is_walk_target_active():
    """True while the walk-target overlay is shown."""
    return _active


# ---------------------------------------------------------------------------
#  StepSpell — minimal Spell duck-type for draw_targeting()
# ---------------------------------------------------------------------------

class StepSpell:
    """Fake spell that shows which adjacent tiles the player can walk to.

    Implements just enough of the ``Spell`` interface for the game's
    ``draw_targeting()`` / ``draw_targeting_borders()`` to work.

    Uses ``level.can_move(player, x, y)`` (no ``teleport``) so walls, chasms,
    occupant-swapping rules, and adjacency (distance <= 1.5) are all respected.
    """

    def __init__(self, caster, level):
        self.caster = caster
        self.level = level
        self.name = "Step"

        # Attributes read by draw_targeting():
        self.melee = True           # range area = 1-tile ball (8 neighbours)
        self.show_tt = True         # draw green/red overlays on in-range tiles
        self.can_target_self = False # skip the player's own tile

    # -- Spell interface used by draw_targeting() --------------------------

    def can_cast(self, x, y):
        """True if the player can walk (or swap) to (x, y) this turn."""
        return self.level.can_move(self.caster, x, y)

    def get_stat(self, attr, base=None):
        """Return fake stats consumed by draw_targeting()."""
        if attr == 'range':
            return 1
        if attr == 'requires_los':
            return False
        return base if base is not None else 0

    def get_impacted_tiles(self, x, y):
        """Only the single target tile is 'impacted'."""
        return [Point(x, y)]

    def get_targetable_tiles(self):
        """All adjacent tiles the player can actually walk to."""
        cx, cy = self.caster.x, self.caster.y
        tiles = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                x, y = cx + dx, cy + dy
                if self.level.is_point_in_bounds(Point(x, y)):
                    if self.can_cast(x, y):
                        tiles.append(Point(x, y))
        return tiles

    # -- Safety: prevent crashes if the game tries to cast this spell ------

    def cast(self, x, y):
        """No-op generator — StepSpell is never actually cast."""
        return
        yield  # make this a generator

    def cast_instant(self, x, y):
        pass

    def can_pay_costs(self):
        return True


# ---------------------------------------------------------------------------
#  Enter / update / exit
# ---------------------------------------------------------------------------

def walk_target_enter(view):
    """Enter walk-target mode: install the StepSpell targeting overlay."""
    global _active, _step_spell

    player = view.game.p1
    level = view.game.cur_level

    _step_spell = StepSpell(player, level)
    view.cur_spell = _step_spell
    view.cur_spell_target = Point(player.x, player.y)
    view.targetable_tiles = _step_spell.get_targetable_tiles()
    view.tab_targets = []
    _active = True
    _log("walk_target: entered")


def walk_target_update(view, ctrl):
    """Called each frame while walk-target is active.

    The left stick / d-pad direction maps directly to the adjacent tile.
    When the stick returns to neutral, the cursor stays at the last aimed
    position so the player can see the green/red feedback and decide.
    """
    if not _active or not _step_spell:
        return

    # Safety: if something else cleared our spell, bail out
    if view.cur_spell is not _step_spell:
        _force_cleanup()
        return

    direction = ctrl.get_combined_direction()
    if direction == (0, 0):
        return  # keep last aimed position

    player = view.game.p1
    dx, dy = direction
    target = Point(player.x + dx, player.y + dy)
    if view.game.cur_level.is_point_in_bounds(target):
        view.cur_spell_target = target
        view.try_examine_tile(target)


def walk_target_exit(view, do_walk=False):
    """Exit walk-target mode.

    If *do_walk* and the target is valid, call ``view.try_move()`` directly
    to execute the step.  Returns True if a move was executed.
    """
    global _active, _step_spell

    moved = False
    if do_walk and _step_spell and view.cur_spell_target:
        player = view.game.p1
        dx = view.cur_spell_target.x - player.x
        dy = view.cur_spell_target.y - player.y

        can_walk = (dx != 0 or dy != 0) and _step_spell.can_cast(
            view.cur_spell_target.x, view.cur_spell_target.y
        )

        # Clear targeting state BEFORE moving so the game doesn't see the
        # dummy spell on the next frame.
        view.cur_spell = None
        view.cur_spell_target = None
        view.targetable_tiles = None
        _step_spell = None
        _active = False

        if can_walk:
            moved = view.try_move(Point(dx, dy))
            _log(f"walk_target: exit walk ({dx},{dy}) moved={moved}")
        elif dx != 0 or dy != 0:
            # Player aimed at an invalid tile — play abort sound
            view.play_sound("menu_abort")
            _log("walk_target: exit cancelled (invalid target)")
        else:
            # Player never aimed (target still on self) — silent cancel
            _log("walk_target: exit cancelled (no aim)")
    else:
        view.cur_spell = None
        view.cur_spell_target = None
        view.targetable_tiles = None
        _step_spell = None
        _active = False
        if do_walk:
            view.play_sound("menu_abort")
        _log("walk_target: exit cancelled")

    return moved


def _force_cleanup():
    """Reset internal state if the spell was removed externally."""
    global _active, _step_spell
    _step_spell = None
    _active = False
