"""Detect monitors and give them human names.

Windows identifies monitors by opaque device paths (``\\\\?\\DISPLAY#GSM5B08#...``)
and Qt by names like ``\\\\.\\DISPLAY1``. There is no documented mapping between
the two, so they are matched by geometry. Resolution always comes from Windows
in physical pixels: Qt reports logical pixels, and rendering at those is the
classic blurry-wallpaper bug on scaled displays.

This module stays free of Qt; the UI passes screen geometry in as plain data.
"""

from __future__ import annotations

import ctypes
import sys
from collections import Counter
from ctypes import wintypes
from dataclasses import dataclass, replace

from wallgen.platform_win.desktop import DesktopWallpaper, open_desktop

# Rounding of fractional scale factors (125%, 175%) can shift a few pixels.
_MATCH_TOLERANCE = 4


@dataclass(frozen=True)
class Monitor:
    device_path: str  # what IDesktopWallpaper.SetWallpaper expects
    left: int
    top: int
    width: int  # physical pixels
    height: int
    label: str = ""

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    @property
    def resolution(self) -> str:
        return f"{self.width} x {self.height}"


@dataclass(frozen=True)
class ScreenGeometry:
    """One QScreen, flattened: its name and logical geometry plus scale."""

    label: str
    x: int
    y: int
    width: int
    height: int
    ratio: float = 1.0


def enumerate_monitors(desktop: DesktopWallpaper) -> list[Monitor]:
    """Attached monitors in reading order (left to right, then top to bottom).

    Windows also lists monitors it remembers but that are unplugged; those
    have empty IDs or empty rectangles and are skipped.
    """
    monitors = []
    for device_path in desktop.monitor_ids():
        if not device_path:
            continue
        try:
            left, top, right, bottom = desktop.monitor_rect(device_path)
        except OSError:
            continue
        if right > left and bottom > top:
            monitors.append(Monitor(device_path, left, top, right - left, bottom - top))
    return sorted(monitors, key=lambda m: (m.left, m.top))


def _distance(monitor: Monitor, screen: ScreenGeometry) -> int:
    width, height = round(screen.width * screen.ratio), round(screen.height * screen.ratio)
    # Qt 6 keeps a screen's top-left in native pixels and scales only its size,
    # but older setups scale both. Accept whichever origin fits.
    origins = {(screen.x, screen.y), (round(screen.x * screen.ratio), round(screen.y * screen.ratio))}
    return min(
        abs(monitor.left - x) + abs(monitor.top - y)
        + abs(monitor.width - width) + abs(monitor.height - height)
        for x, y in origins
    )


def label_monitors(monitors: list[Monitor], screens: list[ScreenGeometry]) -> list[Monitor]:
    """Name each monitor after the Qt screen at the same place and size.

    Unmatched monitors become "Display N". Repeated names get a number so
    two identical panels stay distinguishable.
    """
    pairs = sorted(
        (_distance(monitor, screen), m, s)
        for m, monitor in enumerate(monitors)
        for s, screen in enumerate(screens)
        if screen.label.strip()
    )
    names: dict[int, str] = {}
    taken: set[int] = set()
    for distance, m, s in pairs:
        if distance <= _MATCH_TOLERANCE and m not in names and s not in taken:
            names[m] = screens[s].label.strip()
            taken.add(s)

    labels = [names.get(m, f"Display {m + 1}") for m in range(len(monitors))]
    totals, seen = Counter(labels), Counter()
    result = []
    for monitor, label in zip(monitors, labels):
        if totals[label] > 1:
            seen[label] += 1
            label = f"{label} ({seen[label]})"
        result.append(replace(monitor, label=label))
    return result


def detect_monitors(screens: list[ScreenGeometry]) -> list[Monitor]:
    """Connected monitors with physical sizes, or [] where per-monitor is unsupported."""
    desktop = open_desktop()
    if desktop is None:
        return []
    try:
        monitors = enumerate_monitors(desktop)
    except OSError:
        return []
    return label_monitors(monitors, screens)


_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
_PROCESS_PER_MONITOR_DPI_AWARE = 2


def enable_dpi_awareness() -> None:
    """Make Windows report physical pixels. Call before QApplication exists.

    Uses the same per-monitor v2 mode Qt 6 picks, so Qt's own later attempt is
    a no-op rather than a downgrade. Failure is harmless: Qt still sets it.
    """
    if sys.platform != "win32":
        return
    try:
        set_context = ctypes.WinDLL("user32").SetProcessDpiAwarenessContext
        set_context.argtypes = [ctypes.c_void_p]
        set_context.restype = wintypes.BOOL
        if set_context(ctypes.c_void_p(_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)):
            return
    except (AttributeError, OSError):
        pass  # Windows older than 10 1703
    try:
        ctypes.WinDLL("shcore").SetProcessDpiAwareness(_PROCESS_PER_MONITOR_DPI_AWARE)
    except (AttributeError, OSError):
        pass
