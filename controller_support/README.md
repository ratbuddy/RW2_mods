# Controller Support Mod for Rift Wizard 2

Adds full Xbox / XInput gamepad support to Rift Wizard 2 via a mod. Works alongside keyboard and mouse — you can switch between them at any time.

## Installation

The mod is already in place at `mods/controller_support/`. It loads automatically when the game starts. To disable it, rename the folder or the `.py` file (e.g. add `.disabled` to the filename).

## Requirements

- Any XInput-compatible controller (Xbox One, Xbox Series, or similar)
- The controller should be connected before launching the game, or it will be detected on the next frame it's plugged in

---

## Control Scheme

### Gameplay (Level State)

| Button                 | Action                                                           |
| ---------------------- | ---------------------------------------------------------------- |
| **Left Stick / D-pad** | Move (8 directions)                                              |
| **Right Stick**        | Grid cursor — aim spells or examine tiles                        |
| **A**                  | Confirm / Cast spell at cursor / Deploy / Hold to walk-target    |
| **B**                  | Cancel current spell / Abort deploy / Open options menu          |
| **X**                  | Pass turn / Channel                                              |
| **Y**                  | Open character sheet                                             |
| **RB**                 | Open **spell browser** (see below)                               |
| **LB**                 | Open **item browser** (see below)                                |
| **RT**                 | Interact (enter portals, open shops) / Cast when spell is active |
| **LT**                 | Reroll rifts                                                     |
| **Start**              | Open options menu                                                |
| **Back / Select**      | Show help                                                        |
| **Left Stick Click**   | Autopickup items                                                 |
| **Right Stick Click**  | Toggle threat zone display                                       |

### Spell Browser (RB)

Press **RB** to enter the spell browser. This is a modal cycling menu that uses the game's native UI — you'll see each spell's targeting range overlay and full info in the examine panel as you browse.

| Button                   | Action                                                               |
| ------------------------ | -------------------------------------------------------------------- |
| **RB**                   | Open the spell browser (selects your first spell)                    |
| **D-pad Up / Down**      | Cycle through your spell list (wraps around)                         |
| **Left Stick Up / Down** | Also cycles through spells                                           |
| **A**                    | Confirm selection — locks the spell in and enters **targeting mode** |
| **B**                    | Cancel — deselects the spell and closes the browser                  |
| **RB** (again)           | Cancel — same as B                                                   |

Once you confirm with **A**, you're in targeting mode:

- Use the **Right Stick** to move the targeting cursor tile-by-tile
- Press **A** to cast at the cursor position
- Press **RB** to tab through valid targets
- Press **B** to cancel the spell

### Item Browser (LB)

Works identically to the spell browser but for your consumable items.

| Button              | Action                                                 |
| ------------------- | ------------------------------------------------------ |
| **LB**              | Open the item browser (selects your first item)        |
| **D-pad Up / Down** | Cycle through your items                               |
| **A**               | Confirm selection — enters targeting mode for the item |
| **B**               | Cancel                                                 |
| **LB** (again)      | Cancel — same as B                                     |

### Targeting Mode

When a spell or item is active (selected via browser or any other means):

| Input                  | Action                                          |
| ---------------------- | ----------------------------------------------- |
| **Right Stick**        | Move targeting cursor tile-by-tile on the grid  |
| **Left Stick / D-pad** | Also moves the cursor (same as keyboard arrows) |
| **A**                  | Cast / use at cursor position                   |
| **RT**                 | Cast / use at cursor position (alternative)     |
| **B**                  | Cancel the spell                                |
| **RB**                 | Tab to next valid target                        |

### Walk-Target Mode (Hold A)

When no spell is active during your turn, **hold A** to enter a 1-tile walk-targeting overlay. The game's own red/green tile highlights appear around the player:

- **Green tiles** — the player can walk there (or swap with an ally)
- **Red tiles** — blocked by walls, chasms, enemies, or other obstacles

While holding A, point the **left stick** or **d-pad** in any of the 8 directions to select an adjacent tile. The cursor snaps instantly — no auto-repeat needed. Release **A** to walk to the highlighted tile, or press **B** to cancel.

| Input                   | Action                                  |
| ----------------------- | --------------------------------------- |
| **Hold A**              | Enter walk-target mode (shows overlays) |
| **Left Stick / D-pad**  | Select adjacent tile                    |
| **Release A**           | Walk to the selected tile               |
| **B** (while holding A) | Cancel without moving                   |

> **Note:** Walk-target only activates when no spell is selected and it's the player's turn. In all other contexts, **A** works as normal confirm.

---

### Menus & Navigation

These controls apply across all menu screens (title, options, character sheet, shop, etc.):

| Button                 | Action                     |
| ---------------------- | -------------------------- |
| **Left Stick / D-pad** | Navigate menu options      |
| **A**                  | Confirm / Select           |
| **B**                  | Back / Cancel / Close menu |
| **X**                  | Advance (message screens)  |
| **Start**              | Back / Cancel              |
| **RB**                 | Next tooltip page          |
| **LB**                 | Previous tooltip page      |

#### Title Screen

| Button              | Action             |
| ------------------- | ------------------ |
| **D-pad Up / Down** | Select menu option |
| **A**               | Confirm selection  |

#### Options Menu

| Button                 | Action                              |
| ---------------------- | ----------------------------------- |
| **D-pad Up / Down**    | Navigate options                    |
| **D-pad Left / Right** | Adjust values (volume, speed, etc.) |
| **A**                  | Confirm / Toggle                    |
| **B**                  | Close options                       |

#### Shop / Spell Purchase Screen

| Button                 | Action                           |
| ---------------------- | -------------------------------- |
| **D-pad Up / Down**    | Browse available spells/upgrades |
| **D-pad Left / Right** | Switch pages                     |
| **A**                  | Purchase / Learn                 |
| **B**                  | Close shop                       |

#### Character Sheet

| Button                 | Action                                            |
| ---------------------- | ------------------------------------------------- |
| **D-pad Up / Down**    | Navigate spells / skills / equipment              |
| **D-pad Left / Right** | Switch between spells, skills, and equipment tabs |
| **A**                  | Open upgrade shop for selected spell/skill        |
| **B**                  | Close character sheet                             |

#### Confirm Dialogs

| Button                 | Action            |
| ---------------------- | ----------------- |
| **D-pad Left / Right** | Toggle Yes / No   |
| **A**                  | Confirm selection |
| **B**                  | Select No         |

#### Combat Log

| Button                 | Action               |
| ---------------------- | -------------------- |
| **D-pad Up / Down**    | Scroll log           |
| **D-pad Left / Right** | Previous / Next turn |
| **B**                  | Close log            |

#### Post-Game (Reminisce)

| Button                 | Action                           |
| ---------------------- | -------------------------------- |
| **D-pad Left / Right** | Previous / Next level screenshot |
| **A / X**              | Advance                          |
| **B**                  | Return to title                  |

---

## Configuration

All tunable constants live in `config.py`:

| Setting                  | Default | Description                                                          |
| ------------------------ | ------- | -------------------------------------------------------------------- |
| `STICK_DEADZONE`         | `0.25`  | Radial analog stick deadzone (0.0–1.0)                               |
| `DIRECTION_THRESHOLD`    | `0.15`  | Per-axis threshold after deadzone — lower = easier diagonals         |
| `CURSOR_REPEAT_DELAY`    | `0.30`  | Initial delay before cursor auto-repeats (seconds)                   |
| `CURSOR_REPEAT_INTERVAL` | `0.10`  | Repeat interval for cursor movement (seconds)                        |
| `MOVE_REPEAT_DELAY`      | `0.22`  | Initial delay before movement auto-repeats                           |
| `MOVE_REPEAT_INTERVAL`   | `0.12`  | Repeat interval for movement                                         |
| `DEBOUNCE_TIME`          | `0.07`  | Minimum gap between direction events (prevents stick-bounce doubles) |
| `TRIGGER_THRESHOLD`      | `0.3`   | How far triggers must be pulled to register (0.0–1.0)                |

### Button Mapping

If your controller has non-standard button indices, edit the `XboxButtons` class in `config.py`:

```python
class XboxButtons:
    A = 0
    B = 1
    X = 2
    Y = 3
    LB = 4
    RB = 5
    BACK = 6
    START = 7
    L_STICK = 8
    R_STICK = 9
```

### Axis Mapping (Auto-Detected)

Stick and trigger axes are **auto-detected** at connection time — you should not need to configure them manually. The mod reads each axis's rest value:

- Axes resting near **0.0** → analog sticks (first pair = left, second pair = right)
- Axes resting near **-1.0** → triggers (first = LT, second = RT)

The detected mapping is printed to the console and logged to `controller_support.log`.

## How It Works

The mod monkey-patches every `process_*_input()` method on the game's `PyGameView` class. Before each method runs, the mod:

1. Polls `pygame.joystick` for current controller state
2. Auto-detects axis mapping at connection time (sticks vs triggers) by reading rest values
3. Applies a radial deadzone + per-axis direction threshold for drift-free diagonals
4. Detects button presses (edge-triggered) and analog stick directions with debounce
5. Injects synthetic `pygame.KEYDOWN` events into `self.events` that map to the game's existing keyboard bindings
6. For the right stick targeting cursor, directly manipulates `cur_spell_target` / `deploy_target` for grid-precise aiming

This means the mod is fully compatible with keyboard/mouse input — both work simultaneously.

### File Structure

The mod is split into focused modules:

| File                    | Purpose                                                   |
| ----------------------- | --------------------------------------------------------- |
| `controller_support.py` | Entry point — creates controller, wires modules, patches  |
| `config.py`             | All tunable constants (deadzones, timing, button indices) |
| `log.py`                | File-based logger                                         |
| `game_module.py`        | Game module access, dill alias, KEY_BIND/STATE constants  |
| `controller_state.py`   | Joystick init, auto-detect, polling, edge detection       |
| `repeater.py`           | Direction auto-repeat with debounce                       |
| `helpers.py`            | Shared event-creation utilities                           |
| `browse.py`             | Spell / item browse mode state machine                    |
| `walk_target.py`        | Hold-A walk-target mode (StepSpell + state machine)       |
| `injection.py`          | Main event injection logic                                |
| `patches.py`            | Monkey-patch wrappers for PyGameView methods              |

## Troubleshooting

- **Controller not detected**: Make sure it's plugged in before or during gameplay. The mod checks for new controllers periodically.
- **Wrong button mapping**: The mod prints your controller's name, button count, and axis count to the console on connection. Use this info to adjust the `XboxButtons` constants in `config.py`.
- **Triggers not working**: Axis mapping is auto-detected, but if it fails, check `controller_support.log` for the detected rest values. You can also try adjusting `TRIGGER_THRESHOLD` in `config.py`.
- **Stick drift**: Increase `STICK_DEADZONE` in `config.py` (e.g. to `0.35`).
- **Double inputs / bouncing**: Increase `DEBOUNCE_TIME` in `config.py` (e.g. to `0.10`).
- **Diagonals too hard to hit**: Decrease `DIRECTION_THRESHOLD` in `config.py` (e.g. to `0.10`).
- **Diagnostics**: All axis mappings, button presses, and state changes are logged to `controller_support.log` in the mod folder.
