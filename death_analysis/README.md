# Death Analysis Tool

Parses combat logs from Rift Wizard 2 save directories to analyze how and why runs end. Generates an interactive HTML report with per-run breakdowns and aggregate statistics.

## Features

- **Death floor distribution** — see which floors are deadliest
- **Top killers** — by enemy name and ability
- **Damage sources** — aggregate and per-run damage breakdowns by source and element
- **CC analysis** — tracks Stunned, Frozen, Feared, Silenced, etc. and whether the wizard was CC'd at death
- **Damage spikes** — flags >100 damage received since the wizard's last action
- **Friendly fire** — separately tracks damage from allies
- **Death turn breakdown** — damage taken on the final turn, time since last action
- **Per-run details** — collapsible cards for each run with full damage sources, spells cast, purchases, items used
- **Search/filter** — filter runs by killer, floor, wizard type, or debuff

## Usage

1. Copy `death_analysis.py` into your Rift Wizard 2 game directory (next to the `saves/` folder)
2. Run: `python death_analysis.py`
3. Open the generated `death_analysis_report.html` in a browser

## Requirements

- Python 3.6+
- No external dependencies (stdlib only)

## Notes

- Analyzes runs that reached at least floor 3 and did not end in victory
- Deaths are inferred from the last damage source when no explicit "killed by" line exists in the combat log
- Wizard base HP is 50 (the tool does not track HP pickups)
