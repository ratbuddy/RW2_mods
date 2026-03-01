"""
Controller Support — Logging helper.

Provides a simple file-based logger shared by all modules in the package.
"""

import os

_LOG_PATH = os.path.join(os.path.dirname(__file__), "controller_support.log")

# Start fresh each launch — overwrite any previous log.
try:
    with open(_LOG_PATH, "w", encoding="utf-8") as _f:
        pass  # truncate to zero
except Exception:
    pass


def _log(msg):
    """Append a line to the mod log file. Silently ignores write errors."""
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(str(msg) + "\n")
    except Exception:
        pass
