#!/usr/bin/env bash
# Convenience launcher: sets up the venv on first run, then starts the GUI.
#
# IMPORTANT: uses Python 3.13. PySide6 6.11 crashes on startup under Python
# 3.14 on macOS (SIGABRT in the Qt platform plugin), so we deliberately avoid
# whatever "python3" happens to point at.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON=""
for cand in python3.13 /opt/homebrew/bin/python3.13 /usr/local/bin/python3.13; do
    if command -v "$cand" >/dev/null 2>&1; then PYTHON="$cand"; break; fi
done
if [ -z "$PYTHON" ]; then
    echo "Python 3.13 not found. Install it (e.g. 'brew install python@3.13')." >&2
    echo "Python 3.14 is not supported: PySide6 crashes on startup there." >&2
    exit 1
fi

if [ ! -d .venv ]; then
    echo "Creating virtual environment with $PYTHON…"
    "$PYTHON" -m venv .venv
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements.txt
fi

exec .venv/bin/python mybinder.py
