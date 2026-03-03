# Floating Damage Numbers

Displays floating damage numbers above units when they take damage. Numbers rise upward and fade out, tinted by damage type color (red for fire, blue for ice, etc.). Healing from negative resistance is shown in green with a "+" prefix.

## Installation

Copy the `floating_damage_numbers` folder into your `mods/` directory.

## Configuration

Edit the constants at the top of `floating_damage_numbers.py` to customize:

- `FLOAT_SPEED` — How fast numbers drift upward (default: 1.0)
- `TOTAL_FRAMES` — How long numbers last (default: 40, ~1.3 sec)
- `FADE_START_FRAC` — When fade-out begins (default: 0.5 = halfway)
- `FONT_SIZE` — Text size in pixels (default: 16)
- `X_SCATTER` / `Y_SCATTER` — Random position offset so simultaneous hits don't overlap
- `SHOW_ZERO_DAMAGE` — Whether to show "0" for fully resisted hits (default: False)
- `OUTLINE` — Black text outline for readability (default: True)
- `HEAL_COLOR` — RGB color for healing numbers (default: green)
