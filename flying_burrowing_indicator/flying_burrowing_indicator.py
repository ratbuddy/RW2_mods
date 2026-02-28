# mods/flying_burrowing_indicator/flying_burrowing_indicator.py
# Flying / Burrowing Indicator mod for Rift Wizard 2 by ratbuddy
#
# License / Disclaimer:
#   This code is free to use, share, and modify however you like.
#   No permission needed, no credit required.
#   It comes with absolutely no warranty — use at your own risk.
# ------------------------------------------------------------
# Shows "Flying" and/or "Burrowing" tags on the wizard's left-side
# character panel, just above the resistances section.  Matches the
# style already used for monsters in the examine panel.
#
# Logs to mods/flying_burrowing_indicator/flying_burrowing_indicator.log

import sys, os

LOG_PATH = os.path.join(os.path.dirname(__file__), "flying_burrowing_indicator.log")
def _log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

_log("flying_burrowing_indicator: importing")

# Grab the running game module
game = sys.modules.get("__main__")
if game is None:
    import RiftWizard2 as game
    _log("flying_burrowing_indicator: imported RiftWizard2")

PyGameView = getattr(game, "PyGameView", None)
if PyGameView is None:
    _log("flying_burrowing_indicator: ERROR: PyGameView not found")
    raise RuntimeError("PyGameView not found; game version mismatch?")

# ---------- monkey-patch draw_character ----------

_original_draw_character = PyGameView.draw_character

def _patched_draw_character(self):
    """
    Call the original draw_character, then draw Flying / Burrowing tags
    on the character panel just below the stun line (the last sequentially-
    positioned content before the absolutely-positioned bottom bar).

    We recompute the original layout's cur_y to find exactly where the
    stun line ends, then draw our tags there.
    """
    # Run the original first to draw everything
    _original_draw_character(self)

    p1 = self.game.p1

    # Only draw if the wizard actually has flying or burrowing
    if not p1.flying and not p1.burrowing:
        return

    from Level import BUFF_TYPE_BLESS, BUFF_TYPE_CURSE, BUFF_TYPE_PASSIVE, Tags, Stun
    SPRITE_SIZE = getattr(game, 'SPRITE_SIZE', 16)

    # --- Recompute cur_y by mirroring the original draw_character layout ---
    cur_x = self.border_margin
    cur_y = self.border_margin
    linesize = self.linesize

    # HP line
    cur_y += linesize

    # Shields line (conditional)
    if p1.shields:
        cur_y += linesize

    # SP line
    cur_y += linesize

    # Realm/Turn line
    cur_y += linesize

    # "TODO- buffs here" blank line
    cur_y += linesize

    # "Spells:" header
    cur_y += linesize

    # Each spell
    cur_y += linesize * len(p1.spells)

    # Blank line after spells
    cur_y += linesize

    # "Items:" header
    cur_y += linesize

    # Each item
    cur_y += linesize * len(p1.items)

    # Buffs section
    status_effects = [b for b in p1.buffs if b.buff_type in [BUFF_TYPE_BLESS, BUFF_TYPE_CURSE]]
    if status_effects:
        counts = {}
        for effect in status_effects:
            if effect.name not in counts:
                counts[effect.name] = effect
        cur_y += linesize  # blank line
        cur_y += linesize  # "Status Effects:" header
        cur_y += linesize * len(counts)  # each unique buff

    # Equipment section
    if p1.equipment or p1.trinkets:
        cur_y += linesize  # blank line
        cur_y += linesize  # "Equipment:" header

        from Level import ITEM_SLOT_STAFF, ITEM_SLOT_ROBE, ITEM_SLOT_HEAD, ITEM_SLOT_GLOVES, ITEM_SLOT_BOOTS
        item_list = []
        for slot in [ITEM_SLOT_STAFF, ITEM_SLOT_ROBE, ITEM_SLOT_HEAD, ITEM_SLOT_GLOVES, ITEM_SLOT_BOOTS]:
            item = p1.equipment.get(slot)
            if item:
                item_list.append(item)
        item_list.extend(p1.trinkets)

        # Equipment icons laid out horizontally, wrapping
        eq_x = self.border_margin
        for item in item_list:
            eq_x += SPRITE_SIZE + 2
            if eq_x > self.character_display.get_width() - self.border_margin - SPRITE_SIZE:
                eq_x = self.border_margin
                cur_y += linesize

        cur_y += linesize  # after equipment row

    # Skills section
    skills = [b for b in p1.buffs if b.buff_type == BUFF_TYPE_PASSIVE and not b.prereq]
    if skills:
        cur_y += linesize  # blank line
        cur_y += linesize  # "Skills:" header

        skill_x = self.border_margin
        for skill in skills:
            skill_x += SPRITE_SIZE + 2
            if skill_x > self.character_display.get_width() - self.border_margin - SPRITE_SIZE:
                skill_x = self.border_margin
                cur_y += linesize

        cur_y += linesize  # after skills row

    # Resistances section
    resist_tags = [t for t in Tags if t in p1.resists and p1.resists[t] != 0]
    resist_tags.sort(key=lambda t: -p1.resists[t])

    cur_y += linesize  # blank line before resists
    for negative in [False, True]:
        has_resists = False
        for tag in resist_tags:
            if not ((p1.resists[tag] < 0) == negative):
                continue
            has_resists = True
            cur_y += linesize

        if has_resists:
            cur_y += linesize

    # Stun line (conditional)
    stunbuff = p1.get_buff(Stun)
    if stunbuff:
        cur_y += linesize

    # --- cur_y is now right after the last sequentially-drawn content ---
    # Draw our Flying / Burrowing tags here
    cur_x = self.border_margin
    tag_color = (255, 255, 255)

    if p1.flying:
        self.draw_string("Flying", self.character_display, cur_x, cur_y, tag_color)
        cur_y += linesize

    if p1.burrowing:
        self.draw_string("Burrowing", self.character_display, cur_x, cur_y, tag_color)
        cur_y += linesize

    # Re-blit character display to screen
    self.screen.blit(self.character_display, (0, 0))

PyGameView.draw_character = _patched_draw_character
_log("flying_burrowing_indicator: draw_character patched successfully")
