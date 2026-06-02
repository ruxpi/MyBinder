#!/usr/bin/env python3
"""Launcher for the MyBinder desktop app."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main_window import main

if __name__ == "__main__":
    raise SystemExit(main())
