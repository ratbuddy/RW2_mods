# Steam Deck Panels — Rift Wizard 2

Collapsible side panels and a zoomable/scrollable level viewport for
improved Steam Deck and small-screen playability.

## Installation

Place the `deck_panels` folder inside `RiftWizard2/mods/`.

For controller support, also install the `controller_support` mod.
The `deck_panels` mod must load **after** `controller_support` (mods
load alphabetically, so `d` > `c` — this works by default).

## Controls

### Keyboard / Mouse

| Key            | Action                              |
|----------------|-------------------------------------|
| F9             | Toggle both panels                  |
| F10            | Toggle left panel (wizard stats)    |
| F11            | Toggle right panel (examine info)   |
| F7             | Zoom in                             |
| F8             | Zoom out                            |
| Mouse wheel    | Zoom in/out (on level, not aiming)  |

### Controller (with controller_support mod)

| Combo            | Action              |
|------------------|----------------------|
| Back + LB        | Toggle left panel    |
| Back + RB        | Toggle right panel   |
| Back + Y         | Toggle both panels   |
| Back + D-pad Up  | Zoom in              |
| Back + D-pad Dn  | Zoom out             |
| Right stick      | Scroll camera        |

Right stick scrolling activates automatically whenever the level is
expanded (panels collapsed) or zoomed in.

When you open the spell or item browser (LB/RB on the controller),
the left panel automatically slides back in so you can see the
browse list.

## How It Works

RW2 renders the 33×33 level grid at 16 px per tile into a 528×528
`level_display` surface, then 2× scales it to fill the 1920×1080
screen.  Side panels are blitted on top.

When panels collapse, this mod:

1. Lets the original `draw_level` render everything normally.
2. Crops the native-res `level_display` through a virtual viewport
   camera, upscales the crop to fill the freed screen space, and
   blits it over the standard 2× result.
3. Panels draw on top as usual, naturally layering correctly.

Mouse hit-testing, click margins, and surface positions are all
patched so gameplay input works correctly in the expanded view.

## File Overview

| File                 | Purpose                                 |
|----------------------|-----------------------------------------|
| `deck_panels.py`     | Entry point (loaded by mod system)      |
| `patches.py`         | Monkey-patches for rendering and input  |
| `panel_state.py`     | Panel open/close animation state        |
| `viewport.py`        | Zoom level and camera state             |
| `controller_hooks.py`| Controller combo integration            |
| `game_module.py`     | Shared imports and constants            |
| `__init__.py`        | Package marker                          |
