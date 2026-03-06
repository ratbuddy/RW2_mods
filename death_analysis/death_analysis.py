#!/usr/bin/env python3
"""
Rift Wizard 2 Death Analysis Tool
Parses combat logs from save directories to analyze how and why runs end.
Generates an HTML report with per-run breakdowns and aggregate statistics.
"""

import os
import re
import html
from collections import Counter, defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
SAVES_DIR = os.path.join(SCRIPT_DIR, "saves")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "death_analysis_report.html")

# Minimum floor a run must have reached (finished) to be included in analysis.
# A save qualifies if it has level_N_finish.png for this value of N.
MIN_FLOOR = 3

# Debuff names that indicate crowd control or harmful status effects
CC_DEBUFFS = {
    "Stunned",
    "Frozen",
    "Petrified",
    "Feared",
    "Blind",
    "Silenced",
    "Sleeping",
    "Paralyzed",
    "Confused",
    "Charmed",
    "Rooted",
    "Fear",
}

# Status effects we consider buffs (not debuffs)
KNOWN_BUFFS = {
    "Clarity",
    "Channeling",
    "Mystic Vision",
    "Truesight",
    "Quickstep",
    "Regeneration",
    "Purity",
    "Shielding Shard",
    "Stoneskin",
    "Ice Protection",
    "Fire Protection",
    "Lightning Protection",
    "Dark Immunity",
    "Poison Immunity",
    "Fire Aura",
    "Raven Eye",
    "Stormglass Eye",
    "Golden Dragonscale",
    "Elephant Form",
    "Hag Heart",
    "Eye of Fire",
    "Eye of Ice",
    "Eye of Lightning",
    "Arcane Woven",
    "Astral Phylactery",
    "Sorcery Damage Bonus",
    "Relocator Beacon",
}


def get_qualifying_saves(saves_dir):
    """Return list of save directory paths that reached MIN_FLOOR and are not victories."""
    qualifying = []
    if not os.path.isdir(saves_dir):
        print(f"Saves directory not found: {saves_dir}")
        return qualifying

    for entry in os.listdir(saves_dir):
        save_path = os.path.join(saves_dir, entry)
        if not os.path.isdir(save_path):
            continue
        try:
            save_id = int(entry)
        except ValueError:
            continue

        # Must have finished at least MIN_FLOOR
        if not os.path.exists(os.path.join(save_path, f"level_{MIN_FLOOR}_finish.png")):
            continue

        # Check if victory - only check the LAST (highest-numbered) stats file
        is_victory = False
        stats_files = []
        for f in os.listdir(save_path):
            m = re.match(r"stats\.level_(\d+)\.txt", f)
            if m:
                stats_files.append((int(m.group(1)), f))
        if stats_files:
            stats_files.sort()
            _, last_stats = stats_files[-1]
            try:
                with open(
                    os.path.join(save_path, last_stats),
                    "r",
                    encoding="utf-8",
                    errors="replace",
                ) as fh:
                    if "Outcome: VICTORY" in fh.read():
                        is_victory = True
            except OSError:
                pass
        if is_victory:
            continue

        qualifying.append((save_id, save_path))

    qualifying.sort(key=lambda x: x[0])
    return qualifying


def parse_stats_file(save_path):
    """Parse the highest-numbered stats file for the run's final stats."""
    stats_files = []
    for f in os.listdir(save_path):
        m = re.match(r"stats\.level_(\d+)\.txt", f)
        if m:
            stats_files.append((int(m.group(1)), f))

    if not stats_files:
        return {}

    stats_files.sort(key=lambda x: x[0])
    highest_level, filename = stats_files[-1]

    result = {
        "death_floor": highest_level,
        "floors_completed": len(stats_files),
        "wizard_type": "",
        "outcome": "",
        "turns_local": 0,
        "turns_global": 0,
        "damage_to_wizard": {},
        "damage_to_enemies": {},
        "spell_casts": {},
        "purchases": [],
        "items_used": {},
    }

    try:
        with open(
            os.path.join(save_path, filename), "r", encoding="utf-8", errors="replace"
        ) as fh:
            content = fh.read()
    except OSError:
        return result

    lines = content.strip().split("\n")
    section = None
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        if line.startswith("Realm"):
            pass
        elif (
            i == 1 and not line.startswith("Outcome:") and not line.startswith("Turns")
        ):
            # Line 2 is the wizard type/build name in RW2
            result["wizard_type"] = line
        elif line.startswith("Outcome:"):
            result["outcome"] = line.split(":", 1)[1].strip()
        elif line.startswith("Turns taken:"):
            section = "turns"
        elif line.startswith("Spell Casts:"):
            section = "spells"
        elif line.startswith("Damage to Enemies:"):
            section = "dmg_enemies"
        elif line.startswith("Damage to Wizard:"):
            section = "dmg_wizard"
        elif line.startswith("Purchases:"):
            section = "purchases"
        elif line.startswith("Items Used:"):
            section = "items"
        elif section == "turns":
            m = re.match(r"(\d+)\s+\(([LG])\)", line)
            if m:
                if m.group(2) == "L":
                    result["turns_local"] = int(m.group(1))
                else:
                    result["turns_global"] = int(m.group(1))
        elif section == "spells":
            m = re.match(r"(\d+)\s+(.+)", line)
            if m:
                result["spell_casts"][m.group(2).strip()] = int(m.group(1))
        elif section == "dmg_enemies":
            m = re.match(r"(\d+)\s+(.+)", line)
            if m:
                result["damage_to_enemies"][m.group(2).strip()] = int(m.group(1))
        elif section == "dmg_wizard":
            m = re.match(r"(\d+)\s+(.+)", line)
            if m:
                result["damage_to_wizard"][m.group(2).strip()] = int(m.group(1))
        elif section == "purchases":
            result["purchases"].append(line)
        elif section == "items":
            m = re.match(r"(\d+)\s+(.+)", line)
            if m:
                result["items_used"][m.group(2).strip()] = int(m.group(1))

    return result


def parse_combat_log(save_path):
    """Parse the main combat_log.txt and return detailed death analysis data."""
    log_path = os.path.join(save_path, "log", "combat_log.txt")
    if not os.path.exists(log_path):
        return None

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return None

    lines = [l.rstrip("\n\r") for l in lines]

    # Patterns
    re_turn = re.compile(r"^Level (\d+), Turn (\d+) begins")
    re_damage_to_wizard = re.compile(
        r"\[(.+?):(\w+)\] deals \[(\d+)_(\w+):(\w+)\] damage to \[Wizard:wizard\] with (.+)"
    )
    re_dot_damage = re.compile(
        r"\[Wizard:wizard\] takes \[(\d+)_(\w+):(\w+)\] damage from (.+)"
    )
    re_wizard_killed = re.compile(r"\[Wizard:wizard\] killed by \[(.+?):(\w+)\] (.+)")
    re_status_applied = re.compile(
        r"(\w[\w\s]*?) applied to \[Wizard:wizard\] for \[(\d+)_turns:duration\]"
    )
    re_wizard_is = re.compile(r"\[Wizard:wizard\] is (\w+)")
    re_wizard_action = re.compile(
        r"^\[Wizard:wizard\] (uses |takes a step|stands still)"
    )
    re_wizard_deals = re.compile(r"^\[Wizard:wizard\] deals ")
    re_wizard_heals = re.compile(r"^\[Wizard:wizard\] heals ")

    current_level = 0
    current_turn = 0

    wizard_active_debuffs = {}
    wizard_last_action_turn = (0, 0)
    damage_since_last_action = 0
    damage_this_turn = 0
    damage_this_turn_sources = []

    all_turns = []
    damage_spikes = []

    death_info = {
        "killed": False,
        "killer_name": None,
        "killer_type": None,
        "kill_ability": None,
        "death_level": None,
        "death_turn": None,
        "debuffs_at_death": [],
        "damage_on_death_turn": 0,
        "damage_sources_on_death_turn": [],
        "turns_since_last_action_at_death": 0,
        "damage_since_last_action_at_death": 0,
    }

    total_damage_to_wizard = 0
    damage_by_source = Counter()
    damage_by_type = Counter()
    friendly_fire_damage = 0
    friendly_fire_sources = Counter()
    enemy_damage = 0
    dot_damage = 0
    dot_sources = Counter()

    total_turns_cced = 0
    cc_events = []

    damage_per_level = defaultdict(int)
    turns_per_level = defaultdict(int)

    wizard_acted_this_turn = False
    last_damage_to_wizard = None

    for line in lines:
        if not line.strip():
            continue

        # Fast path: every interesting pattern has "Wizard:wizard" or starts with "Level "
        if "Wizard:wizard" not in line and not line.startswith("Level "):
            continue

        m = re_turn.match(line)
        if m:
            if current_turn > 0:
                all_turns.append(
                    (
                        current_level,
                        current_turn,
                        damage_this_turn,
                        wizard_acted_this_turn,
                        dict(wizard_active_debuffs),
                    )
                )
                if not wizard_acted_this_turn and current_turn > 0:
                    had_cc = any(d in CC_DEBUFFS for d in wizard_active_debuffs)
                    if had_cc:
                        total_turns_cced += 1

                expired = []
                for dname in wizard_active_debuffs:
                    wizard_active_debuffs[dname] -= 1
                    if wizard_active_debuffs[dname] <= 0:
                        expired.append(dname)
                for dname in expired:
                    del wizard_active_debuffs[dname]

            current_level = int(m.group(1))
            current_turn = int(m.group(2))
            turns_per_level[current_level] += 1
            damage_this_turn = 0
            damage_this_turn_sources = []
            wizard_acted_this_turn = False
            continue

        if re_wizard_action.match(line):
            wizard_acted_this_turn = True
            if damage_since_last_action > 100:
                lvl_a, turn_a = wizard_last_action_turn
                damage_spikes.append(
                    {
                        "level": current_level,
                        "turn": current_turn,
                        "damage": damage_since_last_action,
                        "turns_inactive": (
                            (current_turn - turn_a)
                            if current_level == lvl_a
                            else current_turn
                        ),
                        "from_level": lvl_a,
                        "from_turn": turn_a,
                    }
                )
            wizard_last_action_turn = (current_level, current_turn)
            damage_since_last_action = 0
            continue

        if re_wizard_deals.match(line):
            continue

        if re_wizard_heals.match(line):
            continue

        m = re_wizard_is.match(line)
        if m:
            cc_type = m.group(1)
            cc_events.append((current_level, current_turn, cc_type))
            continue

        m = re_status_applied.search(line)
        if m:
            effect_name = m.group(1).strip()
            duration = int(m.group(2))
            if duration > 0:
                wizard_active_debuffs[effect_name] = duration
            continue

        m = re_damage_to_wizard.search(line)
        if m:
            source_name = m.group(1)
            source_type = m.group(2)
            dmg_amount = int(m.group(3))
            dmg_type = m.group(4)
            ability = m.group(6)

            total_damage_to_wizard += dmg_amount
            damage_by_source[source_name] += dmg_amount
            damage_by_type[dmg_type] += dmg_amount
            damage_this_turn += dmg_amount
            damage_this_turn_sources.append(
                (source_name, source_type, dmg_amount, dmg_type, ability)
            )
            damage_since_last_action += dmg_amount
            damage_per_level[current_level] += dmg_amount

            last_damage_to_wizard = (
                source_name,
                source_type,
                dmg_amount,
                dmg_type,
                ability,
            )

            if source_type == "ally":
                friendly_fire_damage += dmg_amount
                friendly_fire_sources[source_name] += dmg_amount
            else:
                enemy_damage += dmg_amount
            continue

        m = re_dot_damage.match(line)
        if m:
            dmg_amount = int(m.group(1))
            dmg_type = m.group(2)
            source = m.group(4)

            total_damage_to_wizard += dmg_amount
            damage_by_source[source + " (DoT)"] += dmg_amount
            damage_by_type[dmg_type] += dmg_amount
            damage_this_turn += dmg_amount
            damage_this_turn_sources.append(
                (source, "dot", dmg_amount, dmg_type, source)
            )
            damage_since_last_action += dmg_amount
            damage_per_level[current_level] += dmg_amount
            dot_damage += dmg_amount
            dot_sources[source] += dmg_amount
            enemy_damage += dmg_amount
            last_damage_to_wizard = (source, "dot", dmg_amount, dmg_type, source)
            continue

        m = re_wizard_killed.search(line)
        if m:
            death_info["killed"] = True
            death_info["killer_name"] = m.group(1)
            death_info["killer_type"] = m.group(2)
            death_info["kill_ability"] = m.group(3)
            death_info["death_level"] = current_level
            death_info["death_turn"] = current_turn
            death_info["debuffs_at_death"] = list(wizard_active_debuffs.keys())
            death_info["damage_on_death_turn"] = damage_this_turn
            death_info["damage_sources_on_death_turn"] = list(damage_this_turn_sources)

            last_lvl, last_turn = wizard_last_action_turn
            if last_lvl == current_level:
                death_info["turns_since_last_action_at_death"] = (
                    current_turn - last_turn
                )
            else:
                death_info["turns_since_last_action_at_death"] = current_turn
            death_info["damage_since_last_action_at_death"] = damage_since_last_action
            continue

    if not death_info["killed"]:
        death_info["death_level"] = current_level
        death_info["death_turn"] = current_turn
        death_info["debuffs_at_death"] = list(wizard_active_debuffs.keys())
        death_info["damage_on_death_turn"] = damage_this_turn
        death_info["damage_sources_on_death_turn"] = list(damage_this_turn_sources)
        last_lvl, last_turn = wizard_last_action_turn
        if current_level > 0:
            if last_lvl == current_level:
                death_info["turns_since_last_action_at_death"] = (
                    current_turn - last_turn
                )
            else:
                death_info["turns_since_last_action_at_death"] = current_turn
        death_info["damage_since_last_action_at_death"] = damage_since_last_action

        if last_damage_to_wizard:
            death_info["inferred_killer_name"] = last_damage_to_wizard[0]
            death_info["inferred_killer_type"] = last_damage_to_wizard[1]
            death_info["inferred_kill_ability"] = last_damage_to_wizard[4]

    if damage_since_last_action > 100 and not death_info["killed"]:
        lvl_a, turn_a = wizard_last_action_turn
        damage_spikes.append(
            {
                "level": current_level,
                "turn": current_turn,
                "damage": damage_since_last_action,
                "turns_inactive": (
                    (current_turn - turn_a) if current_level == lvl_a else current_turn
                ),
                "from_level": lvl_a,
                "from_turn": turn_a,
            }
        )

    return {
        "death_info": death_info,
        "total_damage_to_wizard": total_damage_to_wizard,
        "damage_by_source": dict(damage_by_source),
        "damage_by_type": dict(damage_by_type),
        "friendly_fire_damage": friendly_fire_damage,
        "friendly_fire_sources": dict(friendly_fire_sources),
        "enemy_damage": enemy_damage,
        "dot_damage": dot_damage,
        "dot_sources": dict(dot_sources),
        "damage_per_level": dict(damage_per_level),
        "turns_per_level": dict(turns_per_level),
        "total_turns_cced": total_turns_cced,
        "cc_events": cc_events,
        "damage_spikes": damage_spikes,
        "total_turns": len(all_turns),
    }


def analyze_save(save_id, save_path):
    """Analyze a single save directory."""
    stats = parse_stats_file(save_path)
    combat = parse_combat_log(save_path)

    if not stats and not combat:
        return None

    return {
        "save_id": save_id,
        "stats": stats,
        "combat": combat,
    }


def h(text):
    """HTML-escape text."""
    return html.escape(str(text))


def generate_html_report(analyses):
    """Generate an HTML report from all analyses."""

    total_runs = len(analyses)
    death_floors = Counter()
    killers = Counter()
    kill_abilities = Counter()
    debuffs_at_death = Counter()
    cc_at_death = Counter()
    wizard_types = Counter()
    all_friendly_fire = Counter()
    total_friendly_fire = 0
    total_enemy_damage_all = 0
    total_damage_all = 0
    damage_types_all = Counter()
    all_damage_spikes = []
    all_cc_events = Counter()
    explicit_kills = 0
    inferred_kills = 0
    quit_deaths = 0
    runs_with_cc_at_death = 0
    total_cc_turns = 0
    total_turns_all = 0
    death_turn_damage = []
    turns_since_action_at_death = []
    damage_since_action_at_death = []
    damage_per_floor_agg = defaultdict(list)
    top_damage_sources = Counter()

    for a in analyses:
        stats = a["stats"]
        combat = a["combat"]

        if stats:
            wizard_types[stats.get("wizard_type", "Unknown") or "Unknown"] += 1
            death_floor = stats.get("death_floor", 0)
            death_floors[death_floor] += 1

        if combat:
            di = combat["death_info"]
            outcome = stats.get("outcome", "") if stats else ""

            if di["killed"]:
                explicit_kills += 1
                killers[di["killer_name"]] += 1
                kill_abilities[f'{di["killer_name"]} - {di["kill_ability"]}'] += 1
            elif outcome == "DEFEAT" and di.get("inferred_killer_name"):
                inferred_kills += 1
                killers[di["inferred_killer_name"]] += 1
                kill_abilities[
                    f'{di["inferred_killer_name"]} - {di["inferred_kill_ability"]}'
                ] += 1
            else:
                quit_deaths += 1
                killers["(Quit/Abandoned)"] += 1

            for db in di.get("debuffs_at_death", []):
                debuffs_at_death[db] += 1
                if db in CC_DEBUFFS:
                    cc_at_death[db] += 1

            if any(d in CC_DEBUFFS for d in di.get("debuffs_at_death", [])):
                runs_with_cc_at_death += 1

            death_turn_damage.append(di.get("damage_on_death_turn", 0))
            turns_since_action_at_death.append(
                di.get("turns_since_last_action_at_death", 0)
            )
            damage_since_action_at_death.append(
                di.get("damage_since_last_action_at_death", 0)
            )

            total_friendly_fire += combat.get("friendly_fire_damage", 0)
            total_enemy_damage_all += combat.get("enemy_damage", 0)
            total_damage_all += combat.get("total_damage_to_wizard", 0)

            for src, dmg in combat.get("friendly_fire_sources", {}).items():
                all_friendly_fire[src] += dmg

            for dtype, dmg in combat.get("damage_by_type", {}).items():
                damage_types_all[dtype] += dmg

            for src, dmg in combat.get("damage_by_source", {}).items():
                top_damage_sources[src] += dmg

            for spike in combat.get("damage_spikes", []):
                all_damage_spikes.append({**spike, "save_id": a["save_id"]})

            for evt in combat.get("cc_events", []):
                all_cc_events[evt[2]] += 1

            total_cc_turns += combat.get("total_turns_cced", 0)
            total_turns_all += combat.get("total_turns", 0)

            for floor, dmg in combat.get("damage_per_level", {}).items():
                turns = combat.get("turns_per_level", {}).get(floor, 1)
                damage_per_floor_agg[floor].append(dmg / max(turns, 1))

    all_damage_spikes.sort(key=lambda s: s["damage"], reverse=True)

    parts = []
    parts.append(
        """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Rift Wizard 2 - Death Analysis Report</title>
<style>
:root {
    --bg: #1a1a2e;
    --surface: #16213e;
    --surface2: #0f3460;
    --accent: #e94560;
    --accent2: #533483;
    --text: #eee;
    --text-dim: #aab;
    --gold: #f0c040;
    --green: #44cc88;
    --red: #e94560;
    --blue: #4488ee;
    --orange: #ee8844;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 20px;
}
h1 {
    text-align: center;
    color: var(--accent);
    font-size: 2em;
    margin-bottom: 5px;
    text-shadow: 0 0 20px rgba(233,69,96,0.3);
}
.subtitle {
    text-align: center;
    color: var(--text-dim);
    margin-bottom: 30px;
    font-size: 0.95em;
}
h2 {
    color: var(--gold);
    border-bottom: 2px solid var(--accent2);
    padding-bottom: 8px;
    margin: 30px 0 15px 0;
    font-size: 1.4em;
}
h3 {
    color: var(--blue);
    margin: 20px 0 10px 0;
    font-size: 1.1em;
}
.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 20px;
    margin-bottom: 20px;
}
.card {
    background: var(--surface);
    border: 1px solid var(--accent2);
    border-radius: 10px;
    padding: 20px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
}
.card h3 { margin-top: 0; }
.stat-big {
    font-size: 2.5em;
    font-weight: bold;
    color: var(--accent);
}
.stat-label {
    color: var(--text-dim);
    font-size: 0.85em;
    text-transform: uppercase;
    letter-spacing: 1px;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0;
    background: var(--surface);
    border-radius: 8px;
    overflow: hidden;
}
th {
    background: var(--surface2);
    color: var(--gold);
    padding: 10px 12px;
    text-align: left;
    font-size: 0.85em;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
td {
    padding: 8px 12px;
    border-top: 1px solid rgba(255,255,255,0.05);
}
tr:hover td { background: rgba(255,255,255,0.03); }
.bar-container {
    background: rgba(255,255,255,0.1);
    border-radius: 4px;
    height: 20px;
    position: relative;
    overflow: hidden;
}
.bar {
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s;
    min-width: 2px;
}
.bar-red { background: linear-gradient(90deg, var(--red), #ff6b6b); }
.bar-blue { background: linear-gradient(90deg, var(--blue), #66aaff); }
.bar-gold { background: linear-gradient(90deg, var(--gold), #ffe066); }
.bar-green { background: linear-gradient(90deg, var(--green), #66eea0); }
.bar-orange { background: linear-gradient(90deg, var(--orange), #ffaa66); }
.bar-label {
    position: absolute;
    right: 6px;
    top: 1px;
    font-size: 0.75em;
    color: white;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.8);
}
.tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.8em;
    margin: 2px;
}
.tag-cc { background: var(--red); color: white; }
.tag-debuff { background: var(--accent2); color: white; }
.tag-buff { background: var(--green); color: black; }
.tag-quit { background: #666; color: white; }
.tag-killed { background: var(--red); color: white; }
.tag-spike { background: var(--orange); color: black; }
.collapsible {
    cursor: pointer;
    user-select: none;
}
.collapsible::before {
    content: '\\25B6 ';
    font-size: 0.8em;
    transition: transform 0.2s;
    display: inline-block;
}
.collapsible.open::before {
    content: '\\25BC ';
}
.collapse-content {
    display: none;
    padding: 10px 0;
}
.collapse-content.open {
    display: block;
}
.spike-alert {
    background: rgba(238, 136, 68, 0.15);
    border-left: 4px solid var(--orange);
    padding: 8px 12px;
    margin: 5px 0;
    border-radius: 0 6px 6px 0;
    font-size: 0.9em;
}
.summary-row {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
}
.summary-row:last-child { border-bottom: none; }
.pct { color: var(--text-dim); font-size: 0.85em; }
details { margin: 5px 0; }
details summary {
    cursor: pointer;
    color: var(--blue);
    padding: 5px 0;
}
details summary:hover { color: var(--gold); }
.run-header {
    background: var(--surface);
    border: 1px solid var(--accent2);
    border-radius: 8px;
    padding: 15px 20px;
    margin: 10px 0;
    cursor: pointer;
}
.run-header:hover { border-color: var(--gold); }
.run-detail {
    background: var(--surface);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 0 0 8px 8px;
    padding: 15px 20px;
    margin: -10px 0 10px 0;
    display: none;
}
.run-detail.open { display: block; }
.flex-row {
    display: flex;
    gap: 10px;
    align-items: center;
    flex-wrap: wrap;
}
.mono { font-family: 'Consolas', 'Courier New', monospace; }
#search-box {
    width: 100%;
    padding: 10px 15px;
    background: var(--surface);
    border: 1px solid var(--accent2);
    border-radius: 8px;
    color: var(--text);
    font-size: 1em;
    margin-bottom: 15px;
}
#search-box:focus { outline: none; border-color: var(--gold); }
</style>
</head>
<body>
<h1>&#9760; Rift Wizard 2 &mdash; Death Analysis Report</h1>
"""
    )

    parts.append(
        f'<p class="subtitle">Analyzed {total_runs} qualifying runs ({MIN_FLOOR}+ floors, non-victories) &bull; Generated from save data</p>'
    )

    # ---- Overview Cards ----
    parts.append("<h2>Overview</h2>")
    parts.append('<div class="grid">')

    avg_death_floor = sum(f * c for f, c in death_floors.items()) / max(total_runs, 1)
    parts.append(
        f"""<div class="card">
        <p class="stat-label">Total Runs Analyzed</p>
        <p class="stat-big">{total_runs}</p>
        <p class="stat-label" style="margin-top:10px">Deaths (Explicit / Inferred / Quits)</p>
        <p>{explicit_kills} / {inferred_kills} / {quit_deaths}</p>
    </div>"""
    )

    parts.append(
        f"""<div class="card">
        <p class="stat-label">Average Death Floor</p>
        <p class="stat-big">{avg_death_floor:.1f}</p>
        <p class="stat-label" style="margin-top:10px">Most Common Death Floor</p>
        <p>Floor {death_floors.most_common(1)[0][0] if death_floors else '?'} ({death_floors.most_common(1)[0][1] if death_floors else 0} runs)</p>
    </div>"""
    )

    cc_death_pct = (runs_with_cc_at_death / max(total_runs, 1)) * 100
    cc_turn_pct = (total_cc_turns / max(total_turns_all, 1)) * 100
    parts.append(
        f"""<div class="card">
        <p class="stat-label">Deaths While CC'd</p>
        <p class="stat-big">{cc_death_pct:.0f}%</p>
        <p>{runs_with_cc_at_death} of {total_runs} runs</p>
        <p class="stat-label" style="margin-top:10px">Turns Spent CC'd</p>
        <p>{total_cc_turns} / {total_turns_all} ({cc_turn_pct:.1f}%)</p>
    </div>"""
    )

    ff_pct = (total_friendly_fire / max(total_damage_all, 1)) * 100
    parts.append(
        f"""<div class="card">
        <p class="stat-label">Total Damage to Wizard</p>
        <p class="stat-big">{total_damage_all:,}</p>
        <p class="stat-label" style="margin-top:10px">Friendly Fire</p>
        <p>{total_friendly_fire:,} ({ff_pct:.1f}%) &bull; Enemy: {total_enemy_damage_all:,}</p>
    </div>"""
    )

    parts.append("</div>")

    # ---- Death Floor Distribution ----
    parts.append("<h2>Death Floor Distribution</h2>")
    parts.append(
        "<table><tr><th>Floor</th><th>Deaths</th><th>%</th><th>Distribution</th></tr>"
    )
    max_floor_deaths = max(death_floors.values()) if death_floors else 1
    for floor in sorted(death_floors.keys()):
        count = death_floors[floor]
        pct = count / max(total_runs, 1) * 100
        bar_w = count / max_floor_deaths * 100
        parts.append(
            f"<tr><td>Floor {floor}</td><td>{count}</td><td>{pct:.1f}%</td>"
            f'<td><div class="bar-container"><div class="bar bar-red" style="width:{bar_w}%"></div>'
            f'<span class="bar-label">{count}</span></div></td></tr>'
        )
    parts.append("</table>")

    # ---- Top Killers ----
    parts.append("<h2>Top Killers</h2>")
    parts.append('<div class="grid">')

    parts.append('<div class="card"><h3>By Enemy Name</h3>')
    parts.append("<table><tr><th>Enemy</th><th>Kills</th><th>%</th></tr>")
    for name, count in killers.most_common(25):
        pct = count / max(total_runs, 1) * 100
        parts.append(f"<tr><td>{h(name)}</td><td>{count}</td><td>{pct:.1f}%</td></tr>")
    parts.append("</table></div>")

    parts.append('<div class="card"><h3>By Kill Ability</h3>')
    parts.append("<table><tr><th>Enemy - Ability</th><th>Kills</th></tr>")
    for name, count in kill_abilities.most_common(25):
        parts.append(f"<tr><td>{h(name)}</td><td>{count}</td></tr>")
    parts.append("</table></div>")

    parts.append("</div>")

    # ---- Top Damage Sources ----
    parts.append("<h2>Top Damage Sources to Wizard (All Runs)</h2>")
    parts.append(
        "<table><tr><th>Source</th><th>Total Damage</th><th>%</th><th></th></tr>"
    )
    max_src_dmg = max(top_damage_sources.values()) if top_damage_sources else 1
    for src, dmg in top_damage_sources.most_common(30):
        pct = dmg / max(total_damage_all, 1) * 100
        bar_w = dmg / max_src_dmg * 100
        parts.append(
            f"<tr><td>{h(src)}</td><td>{dmg:,}</td><td>{pct:.1f}%</td>"
            f'<td><div class="bar-container"><div class="bar bar-orange" style="width:{bar_w}%"></div></div></td></tr>'
        )
    parts.append("</table>")

    # ---- Damage Types ----
    parts.append("<h2>Damage Types Taken</h2>")
    parts.append("<table><tr><th>Type</th><th>Damage</th><th>%</th><th></th></tr>")
    max_type_dmg = max(damage_types_all.values()) if damage_types_all else 1
    colors_map = {
        "Physical": "bar-red",
        "Fire": "bar-orange",
        "Lightning": "bar-gold",
        "Ice": "bar-blue",
        "Dark": "bar-red",
        "Arcane": "bar-blue",
        "Poison": "bar-green",
        "Holy": "bar-gold",
    }
    for dtype, dmg in damage_types_all.most_common():
        pct = dmg / max(total_damage_all, 1) * 100
        bar_w = dmg / max_type_dmg * 100
        bar_class = colors_map.get(dtype, "bar-blue")
        parts.append(
            f"<tr><td>{h(dtype)}</td><td>{dmg:,}</td><td>{pct:.1f}%</td>"
            f'<td><div class="bar-container"><div class="bar {bar_class}" style="width:{bar_w}%"></div></div></td></tr>'
        )
    parts.append("</table>")

    # ---- Friendly Fire ----
    if all_friendly_fire:
        parts.append("<h2>Friendly Fire Breakdown</h2>")
        parts.append(
            f"<p>Total ally damage to wizard across all runs: <strong>{total_friendly_fire:,}</strong> ({ff_pct:.1f}% of all damage taken)</p>"
        )
        parts.append("<table><tr><th>Ally Source</th><th>Damage</th><th>%</th></tr>")
        for src, dmg in all_friendly_fire.most_common(20):
            pct = dmg / max(total_friendly_fire, 1) * 100
            parts.append(
                f"<tr><td>{h(src)}</td><td>{dmg:,}</td><td>{pct:.1f}%</td></tr>"
            )
        parts.append("</table>")

    # ---- CC Analysis ----
    parts.append("<h2>Crowd Control Analysis</h2>")
    parts.append('<div class="grid">')

    parts.append('<div class="card"><h3>CC Events by Type</h3>')
    parts.append("<table><tr><th>CC Type</th><th>Times Applied</th></tr>")
    for cc, count in all_cc_events.most_common():
        parts.append(f"<tr><td>{h(cc)}</td><td>{count}</td></tr>")
    parts.append("</table></div>")

    parts.append('<div class="card"><h3>Debuffs Active at Death</h3>')
    parts.append("<table><tr><th>Debuff</th><th>Runs</th><th>% of Deaths</th></tr>")
    for db, count in debuffs_at_death.most_common():
        pct = count / max(total_runs, 1) * 100
        tag_class = "tag-cc" if db in CC_DEBUFFS else "tag-debuff"
        parts.append(
            f'<tr><td><span class="tag {tag_class}">{h(db)}</span></td><td>{count}</td><td>{pct:.1f}%</td></tr>'
        )
    parts.append("</table></div>")

    parts.append("</div>")

    # ---- Damage Spikes ----
    parts.append("<h2>Damage Spikes (&gt;100 damage since wizard's last action)</h2>")
    if all_damage_spikes:
        parts.append(
            f"<p>Found <strong>{len(all_damage_spikes)}</strong> damage spikes across all runs.</p>"
        )
        parts.append(
            "<table><tr><th>Save</th><th>Floor</th><th>Turn</th><th>Damage</th><th>Turns Inactive</th></tr>"
        )
        for spike in all_damage_spikes[:50]:
            parts.append(
                f'<tr><td>#{spike["save_id"]}</td><td>L{spike["level"]}</td>'
                f'<td>T{spike["turn"]}</td><td class="mono">{spike["damage"]}</td>'
                f'<td>{spike["turns_inactive"]}</td></tr>'
            )
        parts.append("</table>")
    else:
        parts.append("<p>No damage spikes found.</p>")

    # ---- Avg Damage Per Turn By Floor ----
    parts.append("<h2>Average Damage to Wizard Per Turn by Floor</h2>")
    parts.append(
        "<table><tr><th>Floor</th><th>Avg Dmg/Turn</th><th>Runs Sampled</th><th></th></tr>"
    )
    floor_avgs = {}
    for floor in sorted(damage_per_floor_agg.keys()):
        vals = damage_per_floor_agg[floor]
        avg = sum(vals) / len(vals)
        floor_avgs[floor] = avg
    max_avg = max(floor_avgs.values()) if floor_avgs else 1
    for floor in sorted(floor_avgs.keys()):
        avg = floor_avgs[floor]
        n = len(damage_per_floor_agg[floor])
        bar_w = avg / max_avg * 100
        parts.append(
            f"<tr><td>Floor {floor}</td><td>{avg:.1f}</td><td>{n}</td>"
            f'<td><div class="bar-container"><div class="bar bar-red" style="width:{bar_w}%"></div></div></td></tr>'
        )
    parts.append("</table>")

    # ---- Death Turn Analysis ----
    parts.append("<h2>Death Turn Analysis</h2>")
    parts.append('<div class="grid">')

    if death_turn_damage:
        avg_dtd = sum(death_turn_damage) / len(death_turn_damage)
        max_dtd = max(death_turn_damage)
        parts.append(
            f"""<div class="card">
            <h3>Damage on Death Turn</h3>
            <p>Average: <strong>{avg_dtd:.1f}</strong></p>
            <p>Maximum: <strong>{max_dtd}</strong></p>
        </div>"""
        )

    if turns_since_action_at_death:
        avg_tsa = sum(turns_since_action_at_death) / len(turns_since_action_at_death)
        max_tsa = max(turns_since_action_at_death)
        no_action_deaths = sum(1 for t in turns_since_action_at_death if t > 0)
        parts.append(
            f"""<div class="card">
            <h3>Turns Since Last Action at Death</h3>
            <p>Average: <strong>{avg_tsa:.1f}</strong></p>
            <p>Maximum: <strong>{max_tsa}</strong> turns</p>
            <p>Deaths with 0 actions gap: <strong>{total_runs - no_action_deaths}</strong></p>
            <p>Deaths after &ge;1 turn without acting: <strong>{no_action_deaths}</strong> ({no_action_deaths/max(total_runs,1)*100:.1f}%)</p>
        </div>"""
        )

    if damage_since_action_at_death:
        avg_dsa = sum(damage_since_action_at_death) / len(damage_since_action_at_death)
        max_dsa = max(damage_since_action_at_death)
        parts.append(
            f"""<div class="card">
            <h3>Damage Since Last Action at Death</h3>
            <p>Average: <strong>{avg_dsa:.1f}</strong></p>
            <p>Maximum: <strong>{max_dsa}</strong></p>
        </div>"""
        )

    parts.append("</div>")

    # ---- Wizard Type Distribution ----
    if wizard_types:
        parts.append("<h2>Wizard Type Distribution</h2>")
        parts.append("<table><tr><th>Wizard Type</th><th>Runs</th><th>%</th></tr>")
        for wtype, count in wizard_types.most_common():
            pct = count / max(total_runs, 1) * 100
            parts.append(
                f"<tr><td>{h(wtype)}</td><td>{count}</td><td>{pct:.1f}%</td></tr>"
            )
        parts.append("</table>")

    # ---- Per-Run Breakdown ----
    parts.append("<h2>Per-Run Breakdown</h2>")
    parts.append(
        '<input type="text" id="search-box" placeholder="Search runs by killer, floor, debuff, wizard type, save ID..." onkeyup="filterRuns()">'
    )

    for a in analyses:
        save_id = a["save_id"]
        stats = a["stats"]
        combat = a["combat"]
        di = combat["death_info"] if combat else {}

        floor = stats.get("death_floor", "?") if stats else "?"
        wtype = stats.get("wizard_type", "?") if stats else "?"
        outcome = stats.get("outcome", "") if stats else ""

        if di.get("killed"):
            killer = di.get("killer_name", "Unknown")
            ability = di.get("kill_ability", "")
            kill_tag = "tag-killed"
            kill_label = "KILLED"
        elif outcome == "DEFEAT" and di.get("inferred_killer_name"):
            killer = di.get("inferred_killer_name", "Unknown")
            ability = di.get("inferred_kill_ability", "")
            kill_tag = "tag-killed"
            kill_label = "KILLED"
        else:
            killer = "(Quit/Abandoned)"
            ability = ""
            kill_tag = "tag-quit"
            kill_label = "QUIT"

        debuffs = di.get("debuffs_at_death", [])
        dmg_death_turn = di.get("damage_on_death_turn", 0)
        turns_since = di.get("turns_since_last_action_at_death", 0)
        dmg_since = di.get("damage_since_last_action_at_death", 0)

        debuff_tags = ""
        for db in debuffs:
            if db in CC_DEBUFFS:
                debuff_tags += f' <span class="tag tag-cc">{h(db)}</span>'
            elif db not in KNOWN_BUFFS:
                debuff_tags += f' <span class="tag tag-debuff">{h(db)}</span>'

        spike_count = len(combat.get("damage_spikes", [])) if combat else 0
        spike_tag = (
            f' <span class="tag tag-spike">{spike_count} spikes</span>'
            if spike_count
            else ""
        )

        total_dmg = combat.get("total_damage_to_wizard", 0) if combat else 0
        ff_dmg = combat.get("friendly_fire_damage", 0) if combat else 0

        searchable = (
            f"{save_id} {floor} {wtype} {killer} {ability} {' '.join(debuffs)}".lower()
        )

        parts.append(
            f"""
        <div class="run-entry" data-search="{h(searchable)}">
        <div class="run-header" onclick="toggleRun(this)">
            <div class="flex-row">
                <strong>Run #{save_id}</strong>
                <span class="pct">Floor {floor}</span>
                <span class="pct">{h(wtype)}</span>
                <span class="tag {kill_tag}">{kill_label}</span>
                <span>{h(killer)}{(' - ' + h(ability)) if ability else ''}</span>
                {debuff_tags}{spike_tag}
            </div>
        </div>
        <div class="run-detail">
        """
        )

        parts.append('<div class="grid">')

        # RW2: wizard base HP is 50, no automatic scaling per floor
        parts.append(
            f"""<div class="card">
            <h3>Death Summary</h3>
            <div class="summary-row"><span>Floor</span><span>{floor}</span></div>
            <div class="summary-row"><span>Turn</span><span>{di.get('death_turn', '?')}</span></div>
            <div class="summary-row"><span>Base Wizard HP</span><span>50</span></div>
            <div class="summary-row"><span>Killed By</span><span>{h(killer)}</span></div>
            <div class="summary-row"><span>Ability</span><span>{h(ability) if ability else 'N/A'}</span></div>
            <div class="summary-row"><span>Damage on Death Turn</span><span>{dmg_death_turn}</span></div>
            <div class="summary-row"><span>Turns Since Last Action</span><span>{turns_since}</span></div>
            <div class="summary-row"><span>Damage Since Last Action</span><span>{dmg_since}</span></div>
            <div class="summary-row"><span>Total Damage Taken</span><span>{total_dmg:,}</span></div>
            <div class="summary-row"><span>Friendly Fire Damage</span><span>{ff_dmg:,}</span></div>
        </div>"""
        )

        if debuffs:
            parts.append('<div class="card"><h3>Active Effects at Death</h3>')
            for db in debuffs:
                if db in CC_DEBUFFS:
                    parts.append(f'<span class="tag tag-cc">{h(db)}</span> ')
                elif db in KNOWN_BUFFS:
                    parts.append(f'<span class="tag tag-buff">{h(db)}</span> ')
                else:
                    parts.append(f'<span class="tag tag-debuff">{h(db)}</span> ')
            parts.append("</div>")

        parts.append("</div>")

        if combat and combat.get("damage_by_source"):
            parts.append("<details><summary>Damage Sources</summary>")
            parts.append("<table><tr><th>Source</th><th>Damage</th></tr>")
            for src, dmg in sorted(
                combat["damage_by_source"].items(), key=lambda x: -x[1]
            ):
                parts.append(f"<tr><td>{h(src)}</td><td>{dmg:,}</td></tr>")
            parts.append("</table></details>")

        if combat and combat.get("friendly_fire_sources"):
            parts.append("<details><summary>Friendly Fire Detail</summary>")
            parts.append("<table><tr><th>Ally</th><th>Damage</th></tr>")
            for src, dmg in sorted(
                combat["friendly_fire_sources"].items(), key=lambda x: -x[1]
            ):
                parts.append(f"<tr><td>{h(src)}</td><td>{dmg:,}</td></tr>")
            parts.append("</table></details>")

        if combat and combat.get("damage_spikes"):
            parts.append("<details><summary>Damage Spikes</summary>")
            for spike in combat["damage_spikes"]:
                parts.append(
                    f'<div class="spike-alert">Floor {spike["level"]} Turn {spike["turn"]}: '
                    f'<strong>{spike["damage"]} damage</strong> over {spike["turns_inactive"]} turns without acting</div>'
                )
            parts.append("</details>")

        if di.get("damage_sources_on_death_turn"):
            parts.append("<details><summary>Damage Sources on Death Turn</summary>")
            parts.append(
                "<table><tr><th>Source</th><th>Type</th><th>Damage</th><th>Element</th><th>Ability</th></tr>"
            )
            for src_name, src_type, dmg, dtype, ability_name in di[
                "damage_sources_on_death_turn"
            ]:
                type_label = (
                    "Ally"
                    if src_type == "ally"
                    else ("DoT" if src_type == "dot" else "Enemy")
                )
                parts.append(
                    f"<tr><td>{h(src_name)}</td><td>{type_label}</td><td>{dmg}</td><td>{h(dtype)}</td><td>{h(ability_name)}</td></tr>"
                )
            parts.append("</table></details>")

        if stats and stats.get("spell_casts"):
            parts.append("<details><summary>Spells Cast</summary>")
            parts.append("<table><tr><th>Spell</th><th>Casts</th></tr>")
            for spell, casts in sorted(
                stats["spell_casts"].items(), key=lambda x: -x[1]
            ):
                parts.append(f"<tr><td>{h(spell)}</td><td>{casts}</td></tr>")
            parts.append("</table></details>")

        if stats and stats.get("purchases"):
            parts.append("<details><summary>Purchases</summary><ul>")
            for p in stats["purchases"]:
                parts.append(f"<li>{h(p)}</li>")
            parts.append("</ul></details>")

        if stats and stats.get("items_used"):
            parts.append("<details><summary>Items Used</summary>")
            parts.append("<table><tr><th>Item</th><th>Uses</th></tr>")
            for item, uses in sorted(stats["items_used"].items(), key=lambda x: -x[1]):
                parts.append(f"<tr><td>{h(item)}</td><td>{uses}</td></tr>")
            parts.append("</table></details>")

        parts.append("</div></div>")

    parts.append(
        """
<script>
function toggleRun(header) {
    var detail = header.nextElementSibling;
    detail.classList.toggle('open');
}
function filterRuns() {
    var query = document.getElementById('search-box').value.toLowerCase();
    var entries = document.querySelectorAll('.run-entry');
    entries.forEach(function(entry) {
        var searchable = entry.getAttribute('data-search');
        entry.style.display = searchable.indexOf(query) !== -1 ? '' : 'none';
    });
}
</script>
</body>
</html>
"""
    )

    return "".join(parts)


def main():
    print(f"Scanning saves in: {SAVES_DIR}")
    qualifying = get_qualifying_saves(SAVES_DIR)
    print(
        f"Found {len(qualifying)} qualifying saves ({MIN_FLOOR}+ floors, non-victories)"
    )

    if not qualifying:
        print("No qualifying saves found. Exiting.")
        return

    analyses = []
    for i, (save_id, save_path) in enumerate(qualifying):
        result = analyze_save(save_id, save_path)
        if result:
            analyses.append(result)
        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(qualifying)} saves...")

    print(f"Analyzed {len(analyses)} runs")
    print("Generating HTML report...")

    report_html = generate_html_report(analyses)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
        fh.write(report_html)

    print(f"Report saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
