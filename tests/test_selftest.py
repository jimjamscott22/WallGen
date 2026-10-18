import ctypes
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from wallgen import selftest
from wallgen.resources import ICON_PATH


def test_the_icon_ships_in_every_size_windows_uses():
    with Image.open(ICON_PATH) as icon:
        sizes = icon.info["sizes"]
    assert {(16, 16), (24, 24), (32, 32), (48, 48), (256, 256)} <= sizes


def test_self_test_passes_and_writes_its_report(qtbot, tmp_path, capsys):
    assert selftest.run() == 0
    report = (tmp_path / "appdata" / "WallGen" / "self-test.log").read_text(encoding="utf-8")
    assert report.endswith("PASSED\n")
    for name in ("data folder", "app icon", "render pcb", "render codeblock", "main window"):
        assert f"ok    {name}:" in report
    assert capsys.readouterr().out == report


def test_a_failing_check_fails_the_run_and_the_rest_still_run(qtbot, tmp_path, monkeypatch):
    def broken(spec, progress=None):
        raise OSError("font file missing from the bundle")

    monkeypatch.setattr(selftest, "render", broken)
    assert selftest.run() == 1
    report = (tmp_path / "appdata" / "WallGen" / "self-test.log").read_text(encoding="utf-8")
    assert "FAIL  render pcb:" in report and "font file missing from the bundle" in report
    assert "ok    main window:" in report
    assert report.endswith("FAILED\n")


def test_windowed_builds_have_no_stdout(qtbot, monkeypatch):
    monkeypatch.setattr(selftest.sys, "stdout", None)
    assert selftest.run() == 0


class _FakeCOMError(Exception):
    def __init__(self, hresult: int, text: str | None = None):
        super().__init__(hresult, text)
        self.hresult = hresult
        self.text = text


def test_com_check_activates_object_and_reads_monitor_ids(monkeypatch):
    buf = ctypes.create_unicode_buffer("\\\\?\\DISPLAY#GSM5B08#1")
    raw = Mock()
    raw.GetMonitorDevicePathCount.return_value = 1
    raw.GetMonitorDevicePathAt.return_value = ctypes.addressof(buf)
    freed = []
    com = SimpleNamespace(
        COMError=_FakeCOMError,
        create=Mock(return_value=raw),
        free=freed.append,
    )
    monkeypatch.setattr(selftest.desktop, "_com", lambda: com)

    assert selftest._com() == "IDesktopWallpaper active (1 monitor ID(s))"
    com.create.assert_called_once_with()
    raw.GetMonitorDevicePathCount.assert_called_once_with()
    raw.GetMonitorDevicePathAt.assert_called_once_with(0)
    assert freed == [ctypes.addressof(buf)]


def test_com_check_fails_when_activation_raises(qtbot, tmp_path, monkeypatch):
    def fail_create():
        raise _FakeCOMError(-2147221164, "Class not registered")

    com = SimpleNamespace(
        COMError=_FakeCOMError,
        create=fail_create,
        free=lambda addr: None,
    )
    monkeypatch.setattr(selftest.sys, "platform", "win32")
    monkeypatch.setattr(selftest.desktop, "_com", lambda: com)

    assert selftest.run() == 1
    report = (tmp_path / "appdata" / "WallGen" / "self-test.log").read_text(encoding="utf-8")
    assert "FAIL  comtypes:" in report
    assert "Class not registered" in report
    assert report.endswith("FAILED\n")


def test_com_check_fails_when_monitor_query_raises(monkeypatch):
    raw = Mock()
    raw.GetMonitorDevicePathCount.side_effect = _FakeCOMError(-2147467259, "Unspecified error")
    com = SimpleNamespace(
        COMError=_FakeCOMError,
        create=lambda: raw,
        free=lambda addr: None,
    )
    monkeypatch.setattr(selftest.desktop, "_com", lambda: com)

    with pytest.raises(OSError, match="Windows could not count monitors: Unspecified error"):
        selftest._com()

