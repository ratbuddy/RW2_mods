# mods/no_pet/no_pet.py
# Remove Sigil Chest + Exotic Pet Shop from portal rewards in Rift Wizard 2 by ratbuddy
# Odds-correct: we don't replace; we simply remove those entries.
#
# License / Disclaimer:
#   This code is free to use, share, and modify however you like.
#   No permission needed, no credit required.
#   It comes with absolutely no warranty — use at your own risk.
#   If it breaks your game, your save, your computer, or your brain,
#   that’s on you :)


import os

LOG_PATH = os.path.join(os.path.dirname(__file__), "no_pet.log")
def _log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

_log("no_pet: import start")

try:
    import Shrines
    _log("no_pet: Shrines imported")
except Exception as e:
    _log(f"no_pet: ERROR importing Shrines: {e!r}")
    raise

# Identify target callables to remove from any reward/shrine tables
targets = []
for name in ("exotic_pet_chest", "crown_chest"):  # crown_chest == Sigil Chest in this codebase
    fn = getattr(Shrines, name, None)
    if callable(fn):
        targets.append(fn)
        _log(f"no_pet: will remove entries for {name}")
targets = tuple(targets)

def _is_table(obj):
    if not isinstance(obj, (list, tuple)) or not obj:
        return False
    row = obj[0]
    return isinstance(row, (list, tuple)) and row and callable(row[0])

def _filter_table(table, label):
    before = len(table)
    filtered = [row for row in table if row and callable(row[0]) and row[0] not in targets]
    after = len(filtered)
    _log(f"no_pet: filtered {label}: {before} -> {after}")
    return filtered

# Filter any static tables on Shrines (covers RW2’s portal reward table)
for attr_name, attr_val in list(vars(Shrines).items()):
    if _is_table(attr_val):
        try:
            setattr(Shrines, attr_name, _filter_table(attr_val, attr_name))
        except Exception as e:
            _log(f"no_pet: skip {attr_name}: {e!r}")

# Optional: wrap factory functions that might build tables dynamically
def _wrap_factory(fn):
    if not callable(fn) or getattr(fn, "_no_pet_wrapped", False):
        return fn
    def wrapped(*args, **kwargs):
        res = fn(*args, **kwargs)
        if _is_table(res):
            res = _filter_table(res, f"{fn.__name__}()")
        return res
    wrapped._no_pet_wrapped = True
    return wrapped

for name, val in list(vars(Shrines).items()):
    if callable(val) and name.lower().startswith(("roll_", "build_", "get_", "make_")):
        try:
            setattr(Shrines, name, _wrap_factory(val))
            _log(f"no_pet: wrapped factory {name}")
        except Exception as e:
            _log(f"no_pet: wrap failed for {name}: {e!r}")

_log("no_pet: installed (sigils + exotic pets removed)")
