#!/usr/bin/env bash
# Convenience launcher: sets up the venv on first run, then starts the GUI.
# Targets Python 3.14 (falls back to any python3). mybinder.py self-heals a
# damaged PySide6 install on startup, so a flaky Qt won't crash the app.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON=""
for cand in python3.14 /opt/homebrew/bin/python3.14 python3.13 python3; do
    if command -v "$cand" >/dev/null 2>&1; then PYTHON="$cand"; break; fi
done
if [ -z "$PYTHON" ]; then
    echo "No python3 found. Install Python (e.g. 'brew install python@3.14')." >&2
    exit 1
fi

if [ ! -d .venv ]; then
    echo "Creating virtual environment with $PYTHON…"
    "$PYTHON" -m venv .venv
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements.txt
fi

exec .venv/bin/python mybinder.py
