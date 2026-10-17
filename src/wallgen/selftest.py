"""``WallGen.exe --self-test``: check a packaged build works, with nobody watching.

It checks the parts a frozen build most often drops: Qt plugins (the .ico
reader), bundled data files, the engine's fonts and native libraries, and
comtypes. A windowed build has no console, so the report goes to
``<data dir>/self-test.log``. Nothing may escape: an uncaught error in a
windowed build opens a dialog, which would hang an unattended run.
"""

from __future__ import annotations

import sys
import traceback
from collections.abc import Callable
from typing import get_args

from PySide6.QtGui import QIcon

from wallgen.engine import RenderSpec, render
from wallgen.engine.spec import Style
from wallgen.platform_win import desktop
from wallgen.resources import ICON_PATH
from wallgen.store.paths import data_dir, ensure_data_dirs

FLAG = "--self-test"
REPORT_NAME = "self-test.log"


def _icon() -> str:
    sizes = QIcon(str(ICON_PATH)).availableSizes()
    if not sizes:
        raise RuntimeError(f"Qt could not read {ICON_PATH}")
    return f"{len(sizes)} sizes, largest {max(s.width() for s in sizes)}px"


def _window() -> str:
    from wallgen.ui.main_window import MainWindow  # the check includes importing it

    window = MainWindow()
    try:
        found = ", ".join(f"{m.label} {m.resolution}" for m in window.monitors)
        return f"built; monitors: {found or 'none detected'}"
    finally:
        window.controller.wait_for_done()
        window.deleteLater()


def _com() -> str:
    desktop._com()
    return "IDesktopWallpaper declared"


def run() -> int:
    """Run every check, write the report, return a process exit code."""
    checks: list[tuple[str, Callable[[], object]]] = [
        ("data folder", lambda: ensure_data_dirs()),
        ("app icon", _icon),
    ]
    checks += [
        (f"render {style}", lambda style=style: render(RenderSpec(style=style, width=320, height=180)).size)
        for style in get_args(Style)
    ]
    if sys.platform == "win32":
        checks.append(("comtypes", _com))
    checks.append(("main window", _window))

    lines, failed = [], False
    for name, check in checks:
        try:
            lines.append(f"ok    {name}: {check()}")
        except Exception:  # noqa: BLE001 - every failure belongs in the report
            failed = True
            lines.append(f"FAIL  {name}:\n{traceback.format_exc()}")
    lines.append("FAILED" if failed else "PASSED")
    report = "\n".join(lines) + "\n"

    try:
        path = data_dir() / REPORT_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
    except OSError:
        failed = True
    if sys.stdout is not None:  # None in a windowed build
        sys.stdout.write(report)
    return 1 if failed else 0
