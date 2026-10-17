import ctypes
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from wallgen.platform_win import desktop


@pytest.fixture
def windows_api(monkeypatch):
    """The legacy API, with the COM interface unavailable."""
    monkeypatch.setattr(desktop, "open_desktop", lambda: None)
    api = Mock(return_value=1)
    dll = Mock(SystemParametersInfoW=api)
    monkeypatch.setattr(desktop.sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "WinDLL", Mock(return_value=dll), raising=False)
    monkeypatch.setattr(ctypes, "set_last_error", Mock(), raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", Mock(return_value=0), raising=False)
    return api


def test_unicode_absolute_path_and_persistent_broadcast_flags(windows_api, tmp_path):
    path = tmp_path / "壁紙.png"
    path.touch()
    desktop.set_on_all_monitors(path)
    windows_api.assert_called_once_with(0x14, 0, str(path.resolve()), 3)


def test_missing_file_does_not_call_windows(windows_api, tmp_path):
    with pytest.raises(FileNotFoundError):
        desktop.set_on_all_monitors(tmp_path / "missing.png")
    windows_api.assert_not_called()


def test_api_false_without_error_is_not_success(windows_api, tmp_path):
    path = tmp_path / "image.png"
    path.touch()
    windows_api.return_value = 0
    with pytest.raises(OSError, match="Windows could not set"):
        desktop.set_on_all_monitors(path)


def test_api_failure_preserves_windows_error(windows_api, monkeypatch, tmp_path):
    path = tmp_path / "image.png"
    path.touch()
    windows_api.return_value = 0
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 5)
    monkeypatch.setattr(ctypes, "WinError", lambda code: OSError(code, "Access denied"), raising=False)
    with pytest.raises(OSError, match="Access denied"):
        desktop.set_on_all_monitors(path)


def test_non_windows_is_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop.sys, "platform", "linux")
    with pytest.raises(OSError, match="Windows only"):
        desktop.set_on_all_monitors(tmp_path / "unused.png")


class FakeDesktop:
    def __init__(self):
        self.calls = []

    def set_position(self, position):
        self.calls.append(("position", position))

    def set_wallpaper(self, monitor_id, path):
        self.calls.append(("wallpaper", monitor_id, path))


@pytest.fixture
def com(monkeypatch, windows_api):
    fake = FakeDesktop()
    monkeypatch.setattr(desktop, "open_desktop", lambda: fake)
    return fake


def test_all_monitors_prefers_com_with_fill(com, windows_api, tmp_path):
    path = tmp_path / "image.png"
    path.touch()
    desktop.set_on_all_monitors(path)
    assert com.calls == [("position", 4), ("wallpaper", None, str(path.resolve()))]
    windows_api.assert_not_called()


def test_one_monitor_uses_its_device_path(com, tmp_path):
    path = tmp_path / "image.png"
    path.touch()
    desktop.set_on_monitor(path, "\\\\?\\DISPLAY#GSM5B08#1")
    assert com.calls == [("position", 4), ("wallpaper", "\\\\?\\DISPLAY#GSM5B08#1", str(path.resolve()))]


def test_one_monitor_checks_the_file_before_windows(com, tmp_path):
    with pytest.raises(FileNotFoundError):
        desktop.set_on_monitor(tmp_path / "missing.png", "id")
    assert com.calls == []


def test_one_monitor_without_com_is_a_clear_error(windows_api, tmp_path):
    path = tmp_path / "image.png"
    path.touch()
    with pytest.raises(OSError, match="Windows 8"):
        desktop.set_on_monitor(path, "id")
    windows_api.assert_not_called()


def test_one_monitor_off_windows_is_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop.sys, "platform", "linux")
    with pytest.raises(OSError, match="Windows only"):
        desktop.set_on_monitor(tmp_path / "unused.png", "id")


def test_open_desktop_is_none_off_windows(monkeypatch):
    monkeypatch.setattr(desktop.sys, "platform", "linux")
    assert desktop.open_desktop() is None


def test_open_desktop_is_none_without_comtypes(monkeypatch):
    def missing():
        raise ImportError("No module named 'comtypes'")

    monkeypatch.setattr(desktop.sys, "platform", "win32")
    monkeypatch.setattr(desktop, "_com", missing)
    assert desktop.open_desktop() is None


class FakeCOMError(Exception):
    def __init__(self, hresult, text):
        super().__init__(hresult, text)
        self.hresult, self.text = hresult, text


def _wrapped(raw):
    freed = []
    com = SimpleNamespace(COMError=FakeCOMError, free=freed.append)
    return desktop._ComDesktop(raw, com), freed


def test_com_wrapper_copies_and_frees_monitor_ids():
    buffers = [ctypes.create_unicode_buffer("\\\\?\\DISPLAY#A"), None, ctypes.create_unicode_buffer("B")]
    addresses = [ctypes.addressof(b) if b is not None else None for b in buffers]
    raw = Mock()
    raw.GetMonitorDevicePathCount.return_value = 3
    raw.GetMonitorDevicePathAt.side_effect = addresses
    wrapper, freed = _wrapped(raw)
    assert wrapper.monitor_ids() == ["\\\\?\\DISPLAY#A", "", "B"]
    assert freed == [addresses[0], addresses[2]]


def test_com_wrapper_reads_rects():
    raw = Mock()
    raw.GetMonitorRECT.return_value = SimpleNamespace(left=-1920, top=0, right=0, bottom=1080)
    wrapper, _ = _wrapped(raw)
    assert wrapper.monitor_rect("id") == (-1920, 0, 0, 1080)


def test_com_wrapper_turns_com_errors_into_os_errors():
    raw = Mock()
    raw.SetWallpaper.side_effect = FakeCOMError(-2147024891, None)
    wrapper, _ = _wrapped(raw)
    with pytest.raises(OSError, match="0x80070005"):
        wrapper.set_wallpaper("id", "C:/x.png")
