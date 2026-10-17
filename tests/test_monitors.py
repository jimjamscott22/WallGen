import ctypes
from unittest.mock import Mock

import pytest

from wallgen.platform_win import monitors
from wallgen.platform_win.monitors import (
    Monitor,
    ScreenGeometry,
    detect_monitors,
    enable_dpi_awareness,
    enumerate_monitors,
    label_monitors,
)


class FakeDesktop:
    def __init__(self, rects):
        self.rects = rects  # device path -> rect, or an exception to raise

    def monitor_ids(self):
        return list(self.rects)

    def monitor_rect(self, monitor_id):
        rect = self.rects[monitor_id]
        if isinstance(rect, Exception):
            raise rect
        return rect


def test_enumerate_skips_detached_monitors_and_sorts_left_to_right():
    desktop = FakeDesktop({
        "right": (2560, 0, 4480, 1080),
        "": (0, 0, 100, 100),                     # forgotten monitor: no ID
        "unplugged": (0, 0, 0, 0),                # empty rectangle
        "broken": OSError("not attached"),
        "left": (0, 0, 2560, 1440),
    })
    assert enumerate_monitors(desktop) == [
        Monitor("left", 0, 0, 2560, 1440),
        Monitor("right", 2560, 0, 1920, 1080),
    ]


def test_monitor_size_and_resolution_text():
    monitor = Monitor("id", -1920, 0, 1920, 1080)
    assert monitor.size == (1920, 1080)
    assert monitor.resolution == "1920 x 1080"


def test_labels_match_unscaled_screens_by_geometry():
    found = [Monitor("a", 0, 0, 2560, 1440), Monitor("b", 2560, 0, 1920, 1080)]
    screens = [ScreenGeometry("LG 24MK", 2560, 0, 1920, 1080), ScreenGeometry("DELL U2719", 0, 0, 2560, 1440)]
    assert [m.label for m in label_monitors(found, screens)] == ["DELL U2719", "LG 24MK"]


def test_labels_match_a_scaled_screen_with_a_native_origin():
    # Qt 6: a 4K panel at 150% to the right of a 1440p one reports its origin
    # in native pixels and its size in logical pixels.
    found = [Monitor("a", 0, 0, 2560, 1440), Monitor("b", 2560, 0, 3840, 2160)]
    screens = [ScreenGeometry("Main", 0, 0, 2560, 1440), ScreenGeometry("4K", 2560, 0, 2560, 1440, 1.5)]
    assert [m.label for m in label_monitors(found, screens)] == ["Main", "4K"]


def test_labels_match_a_scaled_screen_with_a_scaled_origin():
    found = [Monitor("a", 0, 0, 3840, 2160), Monitor("b", 3840, 0, 3840, 2160)]
    screens = [ScreenGeometry("Left", 0, 0, 2560, 1440, 1.5), ScreenGeometry("Right", 2560, 0, 2560, 1440, 1.5)]
    assert [m.label for m in label_monitors(found, screens)] == ["Left", "Right"]


def test_labels_tolerate_rounding_at_fractional_scale():
    found = [Monitor("a", 0, 0, 2560, 1440)]
    screens = [ScreenGeometry("Laptop", 0, 0, 1463, 823, 1.75)]  # 2560.25 x 1440.25
    assert label_monitors(found, screens)[0].label == "Laptop"


def test_unmatched_or_unnamed_monitors_get_numbered_names():
    found = [Monitor("a", 0, 0, 1920, 1080), Monitor("b", 1920, 0, 1920, 1080)]
    screens = [ScreenGeometry("", 0, 0, 1920, 1080), ScreenGeometry("Elsewhere", 9000, 0, 800, 600)]
    assert [m.label for m in label_monitors(found, screens)] == ["Display 1", "Display 2"]


def test_identical_monitors_are_told_apart():
    found = [Monitor("a", 0, 0, 1920, 1080), Monitor("b", 1920, 0, 1920, 1080)]
    screens = [ScreenGeometry("LG 24MK", 0, 0, 1920, 1080), ScreenGeometry("LG 24MK", 1920, 0, 1920, 1080)]
    assert [m.label for m in label_monitors(found, screens)] == ["LG 24MK (1)", "LG 24MK (2)"]


def test_one_screen_names_only_one_monitor():
    found = [Monitor("a", 0, 0, 1920, 1080), Monitor("b", 0, 0, 1920, 1080)]  # mirrored
    screens = [ScreenGeometry("Mirror", 0, 0, 1920, 1080)]
    assert [m.label for m in label_monitors(found, screens)] == ["Mirror", "Display 2"]


def test_detect_returns_nothing_without_the_com_interface(monkeypatch):
    monkeypatch.setattr(monitors, "open_desktop", lambda: None)
    assert detect_monitors([]) == []


def test_detect_returns_nothing_when_enumeration_fails(monkeypatch):
    desktop = Mock()
    desktop.monitor_ids.side_effect = OSError("RPC unavailable")
    monkeypatch.setattr(monitors, "open_desktop", lambda: desktop)
    assert detect_monitors([]) == []


def test_detect_returns_labeled_physical_monitors(monkeypatch):
    desktop = FakeDesktop({"dell": (0, 0, 2560, 1440)})
    monkeypatch.setattr(monitors, "open_desktop", lambda: desktop)
    assert detect_monitors([ScreenGeometry("DELL", 0, 0, 2560, 1440)]) == [
        Monitor("dell", 0, 0, 2560, 1440, "DELL")
    ]


def test_detect_is_empty_off_windows(monkeypatch):
    monkeypatch.setattr(monitors.sys, "platform", "linux")
    assert detect_monitors([]) == []


def test_dpi_awareness_is_a_no_op_off_windows(monkeypatch):
    windll = Mock()
    monkeypatch.setattr(monitors.sys, "platform", "linux")
    monkeypatch.setattr(ctypes, "WinDLL", windll, raising=False)
    enable_dpi_awareness()
    windll.assert_not_called()


@pytest.fixture
def dlls(monkeypatch):
    user32, shcore = Mock(), Mock()
    monkeypatch.setattr(monitors.sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "WinDLL", lambda name: {"user32": user32, "shcore": shcore}[name], raising=False)
    return user32, shcore


def test_dpi_awareness_prefers_per_monitor_v2(dlls):
    user32, shcore = dlls
    user32.SetProcessDpiAwarenessContext.return_value = 1
    enable_dpi_awareness()
    (context,), _ = user32.SetProcessDpiAwarenessContext.call_args
    assert context.value == ctypes.c_void_p(-4).value
    shcore.SetProcessDpiAwareness.assert_not_called()


def test_dpi_awareness_falls_back_to_shcore(dlls):
    user32, shcore = dlls
    user32.SetProcessDpiAwarenessContext.return_value = 0
    enable_dpi_awareness()
    shcore.SetProcessDpiAwareness.assert_called_once_with(2)


def test_dpi_awareness_survives_missing_apis(dlls):
    user32, shcore = dlls
    del user32.SetProcessDpiAwarenessContext
    shcore.SetProcessDpiAwareness.side_effect = OSError("no shcore")
    enable_dpi_awareness()  # must not raise
