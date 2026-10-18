"""Files shipped inside the package, found the same way in dev and in WallGen.exe.

PyInstaller sets each module's ``__file__`` under its bundle directory, and
the spec copies ``assets`` to the matching place, so one lookup serves both.
"""

from __future__ import annotations

from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"
ICON_PATH = ASSETS / "wallgen.ico"  # regenerate with scripts/make_icon.py
