#!/usr/bin/env bash
# Convenience launcher: sets up the venv on first run, then starts the GUI.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
    echo "Creating virtual environment…"
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
fi

exec .venv/bin/python mybinder.py
