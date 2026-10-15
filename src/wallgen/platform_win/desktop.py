"""Set one wallpaper across all monitors using the legacy Windows API."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

SPI_SETDESKWALLPAPER = 0x0014
SPIF_UPDATEINIFILE = 0x0001
SPIF_SENDCHANGE = 0x0002


def set_on_all_monitors(path: Path) -> None:
    """Apply a saved render. Call on the GUI thread; raise on API failure."""
    if sys.platform != "win32":
        raise OSError("Setting wallpaper is supported on Windows only.")
    path = path.resolve(strict=True)
    if not path.is_file():
        raise OSError(f"Wallpaper is not a file: {path}")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    set_wallpaper = user32.SystemParametersInfoW
    set_wallpaper.argtypes = [wintypes.UINT, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
    set_wallpaper.restype = wintypes.BOOL
    ctypes.set_last_error(0)
    if not set_wallpaper(
        SPI_SETDESKWALLPAPER, 0, str(path), SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
    ):
        error = ctypes.get_last_error()
        if error:
            raise ctypes.WinError(error)
        raise OSError("Windows could not set the wallpaper.")
