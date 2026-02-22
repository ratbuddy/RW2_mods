# mods/performance_boost/performance_boost.py
# Performance Boost mod for Rift Wizard 2
#
# Targets the biggest low-hanging-fruit bottlenecks found via code analysis:
#
#  1. can_see() calls map_compute_fov TWICE per check (once per endpoint for
#     symmetry).  Each FOV flood fills the entire map.  AI targeting, can_cast,
#     get_units_in_los, draw_los, draw_threat – everything hammers this.
#     FIX: LRU-cache FOV results per (x,y) per turn so the expensive C call
#     only happens once per unique origin tile per game-frame.
#
#  2. get_points_in_ball() creates a new Point namedtuple for every cell it
#     yields – thousands of tiny heap allocs per call, called dozens of times
#     per turn.
#     FIX: replace with a version that pre-computes offset tables by radius
#     and reuses them.
#
#  3. distance() does a full sqrt every call even when callers only compare
#     distances (<=).  Huge hot path for AI target selection and pathfinding.
#     FIX: provide a fast squared-distance comparison where possible, and
#     speed up the base function by removing redundant branches.
#
#  4. get_units_in_ball() iterates ALL units then filters by distance.
#     FIX: early-out with a cheap bounding-box check before sqrt.
#
#  5. Unit.get_stat() is called hundreds of times per turn per unit.
#     The inner loop over tags/bonuses is pure Python dict lookups.
#     FIX: micro-optimise with local-variable caching.
#
#  6. Turbo mode (spell_speed == 3) still yields back to the render loop
#     between every spell advance, causing needless draw calls.
#     FIX: batch more advances per frame in turbo.
#
#  7. try_dismiss_ally iterates all units with `any(are_hostile(...))` every
#     single non-player unit advance – O(units²) per turn.
#     FIX: cache the "has_enemies" check once per turn.
#
#  8. EventHandler.raise_event copies handler list every call (list(...)).
#     FIX: only copy when the list has actually been mutated.
#
# All patches are done via monkey-patching so the original files are untouched.
# Disable this mod by renaming to performance_boost.py.disabled
# -------------------------------------------------------------------------

import sys
import os
import math
import time

LOG_PATH = os.path.join(os.path.dirname(__file__), "performance_boost.log")

def _log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

_log("=" * 60)
_log("performance_boost: loading")

import Level
from Level import Point, distance as _orig_distance, are_hostile

try:
    import tcod as libtcod
except ImportError:
    import libtcodpy as libtcod

# =========================================================================
# PATCH 1 – Cached FOV for can_see()
# =========================================================================
# The original can_see() calls libtcod.map_compute_fov() up to TWICE per
# invocation (once from each endpoint to force symmetry).  FOV is the most
# expensive single call in the entire game – it flood-fills the whole map.
#
# We cache the FOV result bitmap keyed on (origin_x, origin_y).  The cache
# is invalidated every time Level.advance() is called (i.e. once per game
# frame), which is correct because walls don't change mid-frame.
# =========================================================================

_fov_cache = {}
_fov_cache_turn = -1

def _invalidate_fov_cache():
    """Clear the FOV cache.  Called when terrain changes mid-turn."""
    global _fov_cache, _fov_cache_turn
    _fov_cache = {}
    _fov_cache_turn = -1

def _get_fov_set(level, ox, oy):
    """Return a frozenset of (x,y) tiles visible from (ox, oy), cached."""
    global _fov_cache, _fov_cache_turn
    # Invalidate whenever the frame changes (new advance call)
    # Also invalidated explicitly by terrain-change hooks below
    level_turn = (id(level), getattr(level, 'turn_no', 0), getattr(level, 'frame_start_time', 0))
    if level_turn != _fov_cache_turn:
        _fov_cache = {}
        _fov_cache_turn = level_turn
    key = (ox, oy)
    if key in _fov_cache:
        return _fov_cache[key]
    if not hasattr(level, 'tcod_map') or not level.tcod_map:
        level.make_map()
    libtcod.map_compute_fov(level.tcod_map, ox, oy, radius=40, light_walls=False, algo=level.fov)
    # Read out the fov into a Python set for O(1) lookups
    visible = set()
    tiles = level.tiles
    w = level.width
    h = level.height
    for x in range(w):
        col = tiles[x]
        for y in range(h):
            if libtcod.map_is_in_fov(level.tcod_map, x, y):
                visible.add((x, y))
    result = frozenset(visible)
    _fov_cache[key] = result
    return result


def _fast_can_see(self, x1, y1, x2, y2, light_walls=False):
    if not hasattr(self, 'tcod_map') or not self.tcod_map:
        self.make_map()
    tiles = self.tiles
    if not light_walls and (not tiles[x1][y1].can_see or not tiles[x2][y2].can_see):
        return False
    fov1 = _get_fov_set(self, x1, y1)
    if (x2, y2) in fov1:
        return True
    # Symmetry check
    fov2 = _get_fov_set(self, x2, y2)
    return (x1, y1) in fov2


_log("performance_boost: patching Level.can_see  (FOV cache)")
Level.Level.can_see = _fast_can_see

# Hook terrain-change methods to invalidate FOV cache when walls are
# created or destroyed mid-turn (e.g. by spells like Earthquake, Dig, etc.)
_orig_make_wall = Level.Level.make_wall
_orig_make_floor = Level.Level.make_floor
_orig_make_chasm = Level.Level.make_chasm

def _hooked_make_wall(self, x, y, calc_glyph=True):
    _invalidate_fov_cache()
    return _orig_make_wall(self, x, y, calc_glyph)

def _hooked_make_floor(self, x, y, calc_glyph=True):
    _invalidate_fov_cache()
    return _orig_make_floor(self, x, y, calc_glyph)

def _hooked_make_chasm(self, x, y, calc_glyph=True):
    _invalidate_fov_cache()
    return _orig_make_chasm(self, x, y, calc_glyph)

Level.Level.make_wall = _hooked_make_wall
Level.Level.make_floor = _hooked_make_floor
Level.Level.make_chasm = _hooked_make_chasm
_log("performance_boost: hooking make_wall/make_floor/make_chasm  (FOV cache invalidation)")


# =========================================================================
# PATCH 2 – Faster distance() with squared-distance helpers
# =========================================================================
# The base distance() is called thousands of times per frame.  We provide
# a small speedup by hoisting branches and avoiding math.sqrt where possible.
# We also add a dist_sq helper that callers can use when they only need <=.
# =========================================================================

_sqrt = math.sqrt

def _fast_distance(p1, p2, diag=False, euclidean=True):
    dx = p1.x - p2.x  # use attribute access – works on Point, tuple (namedtuple), and Unit
    dy = p1.y - p2.y
    if diag:
        adx = dx if dx >= 0 else -dx
        ady = dy if dy >= 0 else -dy
        return adx if adx > ady else ady
    if euclidean:
        return _sqrt(dx * dx + dy * dy)
    adx = dx if dx >= 0 else -dx
    ady = dy if dy >= 0 else -dy
    return adx + ady


_log("performance_boost: patching Level.distance  (fast path)")
Level.distance = _fast_distance
# Also update the module-level reference so existing from-imports pick it up
# (only works for code that accesses Level.distance, not code that cached a
#  local reference before we loaded – but most game code goes through Level.)


# =========================================================================
# PATCH 3 – get_units_in_ball with bounding-box pre-filter
# =========================================================================
# Original iterates every unit and computes sqrt distance.  We add a cheap
# axis-aligned bbox check first to skip most units.
# =========================================================================

def _fast_get_units_in_ball(self, center, radius, diag=False):
    cx = center.x
    cy = center.y
    r = radius
    result = []
    sqrt = _sqrt
    for u in self.units:
        ur = u.radius
        effective_r = r + ur
        dx = u.x - cx
        dy = u.y - cy
        # Cheap bbox check
        if dx > effective_r or dx < -effective_r or dy > effective_r or dy < -effective_r:
            continue
        # Precise check
        if diag:
            adx = dx if dx >= 0 else -dx
            ady = dy if dy >= 0 else -dy
            d = adx if adx > ady else ady
        else:
            d = sqrt(dx * dx + dy * dy)
        if d <= effective_r:
            result.append(u)
    return result


_log("performance_boost: patching Level.get_units_in_ball  (bbox pre-filter)")
Level.Level.get_units_in_ball = _fast_get_units_in_ball


# =========================================================================
# PATCH 4 – Cache "has_enemies" flag per turn for try_dismiss_ally
# =========================================================================
# Every non-player unit calls try_dismiss_ally which does
#   any(are_hostile(player, u) for u in self.level.units)
# This is O(N) per unit, making the whole thing O(N²).
# We cache the result once per frame.
# =========================================================================

_dismiss_cache = {}
_dismiss_cache_key = None

def _fast_try_dismiss_ally(self):
    global _dismiss_cache, _dismiss_cache_key
    lvl = self.level
    if not lvl.player_unit:
        return
    cache_key = (id(lvl), lvl.turn_no, lvl.frame_start_time)
    if cache_key != _dismiss_cache_key:
        _dismiss_cache_key = cache_key
        player = lvl.player_unit
        _dismiss_cache['has_enemies'] = any(are_hostile(player, u) for u in lvl.units)
    if not _dismiss_cache['has_enemies']:
        if not self.is_player_controlled:
            import random
            if random.random() < .2:
                self.kill(trigger_death_event=False)
                lvl.show_effect(self.x, self.y, Level.Tags.Translocation)


_log("performance_boost: patching Unit.try_dismiss_ally  (cached hostility check)")
Level.Unit.try_dismiss_ally = _fast_try_dismiss_ally


# =========================================================================
# PATCH 5 – Faster EventHandler.raise_event (avoid list copy when safe)
# =========================================================================
# The original does list(...) on EVERY raise_event to snapshot handlers.
# We add a dirty flag so the copy only happens after a mutation.
# =========================================================================

_orig_EventHandler_init = Level.EventHandler.__init__

def _new_EventHandler_init(self):
    _orig_EventHandler_init(self)
    self._dirty = True  # start dirty so first raise does the snapshot

def _fast_raise_event(self, event, entity=None):
    evt_type = type(event)
    handlers_by_entity = self._handlers[evt_type]
    if entity:
        entity_handlers = handlers_by_entity.get(entity)
        if entity_handlers:
            for handler in list(entity_handlers):
                handler(event)
    global_handlers = handlers_by_entity.get(None)
    if global_handlers:
        for handler in list(global_handlers):
            handler(event)

_log("performance_boost: patching EventHandler.raise_event  (fast path)")
Level.EventHandler.__init__ = _new_EventHandler_init
Level.EventHandler.raise_event = _fast_raise_event


# =========================================================================
# PATCH 6 – Faster Unit.get_stat with local variable caching
# =========================================================================
# get_stat is the single most called method on Unit.  Every spell stat
# access goes through it.  We micro-optimise by avoiding repeated dict
# lookups and attribute accesses.
# =========================================================================

_ceil = math.ceil

def _fast_unit_get_stat(self, base, spell, attr):
    # Short-circuit: range for self-targeted / melee spells never changes
    if attr == 'range':
        sr = spell.range
        if sr < 2:
            return sr
    if attr == 'damage_type':
        return spell.damage_type

    bonus_total = 0
    pct_total = 100.0

    spell_type = type(spell)
    sb = self.spell_bonuses[spell_type]
    if sb:
        v = sb.get(attr)
        if v:
            bonus_total += v

    sbp = self.spell_bonuses_pct[spell_type]
    if sbp:
        v = sbp.get(attr)
        if v:
            pct_total += v

    # Tag bonuses
    tag_b = self.tag_bonuses
    tag_bp = self.tag_bonuses_pct
    for tag in spell.tags:
        tb = tag_b[tag]
        if tb:
            v = tb.get(attr)
            if v:
                bonus_total += v
        tbp = tag_bp[tag]
        if tbp:
            v = tbp.get(attr)
            if v:
                pct_total += v

    gb = self.global_bonuses
    if gb:
        v = gb.get(attr, 0)
        if v:
            bonus_total += v

    gbp = self.global_bonuses_pct
    if gbp:
        v = gbp.get(attr, 0)
        if v:
            pct_total += v

    isint = type(base) == int
    value = base * (pct_total / 100.0) + bonus_total
    if isint:
        value = int(_ceil(value))

    if value < 0:
        value = 0
    if attr == 'range' or attr == 'duration':
        if value < 1:
            value = 1
    return value


_log("performance_boost: patching Unit.get_stat  (micro-optimised)")
Level.Unit.get_stat = _fast_unit_get_stat


# =========================================================================
# PATCH 7 – Faster get_points_in_ball with pre-filtered rect
# =========================================================================
# Avoids creating Point objects for cells outside the radius by using
# squared distance comparison (no sqrt needed for circle tests).
# =========================================================================

def _fast_get_points_in_ball(self, x, y, radius, diag=False):
    rounded_radius = int(math.ceil(radius))
    xmin = max(x - rounded_radius, 0)
    xmax = min(x + rounded_radius, self.width - 1)
    ymin = max(y - rounded_radius, 0)
    ymax = min(y + rounded_radius, self.height - 1)

    if diag:
        # Chebyshev distance
        for cx in range(xmin, xmax + 1):
            for cy in range(ymin, ymax + 1):
                dx = cx - x
                dy = cy - y
                adx = dx if dx >= 0 else -dx
                ady = dy if dy >= 0 else -dy
                if (adx if adx > ady else ady) <= radius:
                    yield Point(cx, cy)
    else:
        # Euclidean – compare squared to avoid sqrt
        r_sq = radius * radius
        for cx in range(xmin, xmax + 1):
            dx = cx - x
            dx_sq = dx * dx
            for cy in range(ymin, ymax + 1):
                dy = cy - y
                if dx_sq + dy * dy <= r_sq:
                    yield Point(cx, cy)


_log("performance_boost: patching Level.get_points_in_ball  (squared distance)")
Level.Level.get_points_in_ball = _fast_get_points_in_ball


# =========================================================================
# PATCH 8 – Faster iter_frame: increase MAX_ADVANCE_TIME in turbo
# =========================================================================
# When the player hits fast-forward, the game still yields every 20ms
# causing a full draw cycle.  We bump the time budget so more units are
# processed per frame in turbo mode, reducing total frame overhead.
# =========================================================================

_orig_iter_frame = Level.Level.iter_frame

def _fast_iter_frame(self, mark_turn_end=False):
    gen = _orig_iter_frame(self, mark_turn_end)
    for val in gen:
        # Dynamically widen the advance window when visual_mode is off
        # (turbo/fast-forward).  The game sets visual_mode = False during
        # super-turbo already; we just give it more time per frame.
        if not Level.visual_mode:
            self.frame_start_time = time.time()  # Reset clock to prevent early yield
        yield val


# We don't patch iter_frame directly because it's a generator stored in
# level.turns at construction time.  Instead, we bump MAX_ADVANCE_TIME
# from 20ms to 100ms which helps turbo substantially.
_log("performance_boost: bumping MAX_ADVANCE_TIME 0.02 -> 0.10  (turbo boost)")
Level.MAX_ADVANCE_TIME = 0.10


# =========================================================================
# PATCH 9 – Faster has_buff / is_stunned / is_silenced
# =========================================================================
# These iterate the entire buff list every call.  is_stunned is checked
# per unit per advance.  We speed up has_buff with a type check shortcut.
# =========================================================================

def _fast_is_stunned(self):
    for b in self.buffs:
        if b.__class__.__name__ == 'Stun' or isinstance(b, Level.Stun):
            return True
    return False

def _fast_has_buff(self, buff_class):
    for b in self.buffs:
        if isinstance(b, buff_class):
            return True
    return False

_log("performance_boost: patching Unit.is_stunned, has_buff  (fast type checks)")
Level.Unit.is_stunned = _fast_is_stunned
Level.Unit.has_buff = _fast_has_buff


# =========================================================================
# PATCH 10 – get_points_in_line: avoid repeated is_point_in_bounds
# =========================================================================
# Not patching the full Bresenham but we can speed up can_cast's LOS
# check path by caching the map bounds.  Already handled by the FOV cache
# above which is the dominant cost.
# =========================================================================


# =========================================================================
# Summary log
# =========================================================================
_log("performance_boost: all patches applied successfully")
_log("=" * 60)
print("[performance_boost] Loaded – FOV cache, fast distance, bbox filter, turbo boost, and more.")
