#!/usr/bin/env python3
"""Launcher for the MyBinder desktop app.

Includes a self-healing preflight: before loading the GUI we run a tiny
subprocess that tries to bring up Qt. If that aborts (the failure mode that
shows up as a macOS "Python quit unexpectedly" crash — seen with damaged
PySide6 installs), we repair PySide6 once and retry, rather than letting the
main process crash. On a healthy install the check costs a few hundred ms.
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# Tiny program that exits 0 only if Qt can initialize a platform plugin.
_QT_PROBE = (
    "import os; os.environ['QT_QPA_PLATFORM'] = 'offscreen'; "
    "from PySide6.QtWidgets import QApplication; QApplication([])"
)


def _qt_initializes() -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-c", _QT_PROBE],
            capture_output=True,
            timeout=60,
        )
        return result.returncode == 0
    except Exception:
        return False


def _repair_pyside6() -> None:
    print("Qt failed to start — repairing PySide6 (one-time)…", flush=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install",
         "--force-reinstall", "--no-cache-dir", "PySide6"],
        check=False,
    )


def main() -> int:
    if not _qt_initializes():
        _repair_pyside6()
        if not _qt_initializes():
            print(
                "Qt still cannot start. Try recreating the environment:\n"
                "    rm -rf .venv && ./scripts/run.sh",
                file=sys.stderr,
            )
            return 1
    from app.main_window import main as run_app
    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
