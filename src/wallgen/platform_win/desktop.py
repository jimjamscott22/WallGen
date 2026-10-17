"""Set wallpapers through Windows' IDesktopWallpaper COM interface.

IDesktopWallpaper (Windows 8+) can target one monitor at a time. The legacy
SystemParametersInfoW call stays as the fallback for "all monitors" when the
COM object is unavailable. Everything here runs on the GUI thread: COM objects
are apartment-bound, so each call creates and uses its own object right there.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from functools import cache
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol

SPI_SETDESKWALLPAPER = 0x0014
SPIF_UPDATEINIFILE = 0x0001
SPIF_SENDCHANGE = 0x0002

# DESKTOP_WALLPAPER_POSITION. Renders are made at native size, so FILL changes
# nothing until a monitor's resolution changes, and then it fails gracefully.
DWPOS_FILL = 4

CLSID_DESKTOP_WALLPAPER = "{C2CF3110-460E-4FC1-B9D0-8A1C0C9CC4BD}"
IID_DESKTOP_WALLPAPER = "{B92B56A9-8B55-4E14-9A89-0199BBB6F93B}"

Rect = tuple[int, int, int, int]  # left, top, right, bottom in physical pixels


class DesktopWallpaper(Protocol):
    """The small, Pythonic slice of IDesktopWallpaper that WallGen uses."""

    def monitor_ids(self) -> list[str]: ...
    def monitor_rect(self, monitor_id: str) -> Rect: ...
    def set_position(self, position: int) -> None: ...
    def set_wallpaper(self, monitor_id: str | None, path: str) -> None: ...


@cache
def _com() -> SimpleNamespace:
    """Import comtypes and declare the interface once. Windows only."""
    from comtypes import COMMETHOD, GUID, CoCreateInstance, COMError, IUnknown

    POINTER, HRESULT, c_int, c_void_p = ctypes.POINTER, ctypes.HRESULT, ctypes.c_int, ctypes.c_void_p

    class IDesktopWallpaper(IUnknown):
        # Order is load-bearing: comtypes calls vtable slots by position, so
        # these must match shobjidl_core.h exactly. Nothing past GetPosition
        # is declared, so nothing past it may be called.
        _iid_ = GUID(IID_DESKTOP_WALLPAPER)
        _methods_ = [
            COMMETHOD([], HRESULT, "SetWallpaper",
                      (["in"], wintypes.LPCWSTR, "monitorID"),
                      (["in"], wintypes.LPCWSTR, "wallpaper")),
            # Returned strings are CoTaskMemAlloc'd, so they come back as raw
            # pointers that _ComDesktop copies and frees.
            COMMETHOD([], HRESULT, "GetWallpaper",
                      (["in"], wintypes.LPCWSTR, "monitorID"),
                      (["out"], POINTER(c_void_p), "wallpaper")),
            COMMETHOD([], HRESULT, "GetMonitorDevicePathAt",
                      (["in"], wintypes.UINT, "monitorIndex"),
                      (["out"], POINTER(c_void_p), "monitorID")),
            COMMETHOD([], HRESULT, "GetMonitorDevicePathCount",
                      (["out"], POINTER(wintypes.UINT), "count")),
            COMMETHOD([], HRESULT, "GetMonitorRECT",
                      (["in"], wintypes.LPCWSTR, "monitorID"),
                      (["out"], POINTER(wintypes.RECT), "displayRect")),
            COMMETHOD([], HRESULT, "SetBackgroundColor",
                      (["in"], wintypes.DWORD, "color")),
            COMMETHOD([], HRESULT, "GetBackgroundColor",
                      (["out"], POINTER(wintypes.DWORD), "color")),
            COMMETHOD([], HRESULT, "SetPosition",
                      (["in"], c_int, "position")),
            COMMETHOD([], HRESULT, "GetPosition",
                      (["out"], POINTER(c_int), "position")),
        ]

    free = ctypes.WinDLL("ole32").CoTaskMemFree
    free.argtypes = [c_void_p]
    free.restype = None
    return SimpleNamespace(
        COMError=COMError,
        create=lambda: CoCreateInstance(GUID(CLSID_DESKTOP_WALLPAPER), interface=IDesktopWallpaper),
        free=free,
    )


class _ComDesktop:
    """Wraps the raw COM object; turns COMError into OSError for the UI."""

    def __init__(self, obj, com: SimpleNamespace):
        self._obj, self._com = obj, com

    def _call(self, action: str, method, *args):
        try:
            return method(*args)
        except self._com.COMError as exc:
            detail = exc.text or f"HRESULT 0x{exc.hresult & 0xFFFFFFFF:08X}"
            raise OSError(f"Windows could not {action}: {detail}") from exc

    def monitor_ids(self) -> list[str]:
        count = self._call("count monitors", self._obj.GetMonitorDevicePathCount)
        ids = []
        for index in range(count):
            address = self._call("read a monitor ID", self._obj.GetMonitorDevicePathAt, index)
            if not address:
                ids.append("")
                continue
            try:
                ids.append(ctypes.wstring_at(address))
            finally:
                self._com.free(address)
        return ids

    def monitor_rect(self, monitor_id: str) -> Rect:
        rect = self._call("read a monitor's position", self._obj.GetMonitorRECT, monitor_id)
        return rect.left, rect.top, rect.right, rect.bottom

    def set_position(self, position: int) -> None:
        self._call("set the wallpaper fit", self._obj.SetPosition, position)

    def set_wallpaper(self, monitor_id: str | None, path: str) -> None:
        self._call("set the wallpaper", self._obj.SetWallpaper, monitor_id, path)


def open_desktop() -> DesktopWallpaper | None:
    """A fresh IDesktopWallpaper for the calling thread, or None if unavailable."""
    if sys.platform != "win32":
        return None
    try:
        com = _com()
    except ImportError:
        return None
    try:
        return _ComDesktop(com.create(), com)
    except (OSError, com.COMError):
        return None


def _checked(path: Path) -> Path:
    if sys.platform != "win32":
        raise OSError("Setting wallpaper is supported on Windows only.")
    path = path.resolve(strict=True)
    if not path.is_file():
        raise OSError(f"Wallpaper is not a file: {path}")
    return path


def set_on_monitor(path: Path, monitor_id: str) -> None:
    """Apply a saved render to one monitor. Call on the GUI thread."""
    path = _checked(path)
    desktop = open_desktop()
    if desktop is None:
        raise OSError("Per-monitor wallpapers need Windows 8 or later.")
    desktop.set_position(DWPOS_FILL)
    desktop.set_wallpaper(monitor_id, str(path))


def set_on_all_monitors(path: Path) -> None:
    """Apply a saved render everywhere. Call on the GUI thread; raise on failure."""
    path = _checked(path)
    desktop = open_desktop()
    if desktop is not None:
        desktop.set_position(DWPOS_FILL)
        desktop.set_wallpaper(None, str(path))  # NULL monitor ID = every monitor
        return
    _set_with_system_parameters(path)


def _set_with_system_parameters(path: Path) -> None:
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
