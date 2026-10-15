import ctypes
from unittest.mock import Mock

import pytest

from wallgen.platform_win import desktop


@pytest.fixture
def windows_api(monkeypatch):
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
