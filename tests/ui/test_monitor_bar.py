"""The 'Set on' row: detected monitors as chips, and per-monitor setting."""

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from wallgen.engine import RenderSpec
from wallgen.platform_win.monitors import Monitor
from wallgen.ui import main_window
from wallgen.ui.main_window import MainWindow

DELL = Monitor("\\\\?\\DISPLAY#DEL41B5#1", 0, 0, 2560, 1440, "DELL U2719")
ULTRAWIDE = Monitor("\\\\?\\DISPLAY#GSM5B08#2", 2560, 0, 3440, 1440, "LG 34WN")


@pytest.fixture
def detected(monkeypatch):
    found = [DELL, ULTRAWIDE]
    monkeypatch.setattr(main_window, "detect_monitors", lambda screens: list(found))
    return found


@pytest.fixture
def set_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(main_window, "set_on_monitor", lambda path, monitor_id: calls.append((path, monitor_id)))
    return calls


@pytest.fixture
def window(qtbot, tmp_path, detected):
    win = MainWindow(preview_max_width=160, render_directory=tmp_path)
    qtbot.addWidget(win)
    yield win
    win.controller.wait_for_done()


@pytest.fixture
def submitted(window, monkeypatch):
    specs = []
    monkeypatch.setattr(window.controller, "submit", specs.append)
    return specs


def show_render(window, tmp_path, size=(2560, 1440), name="render"):
    window._on_full_ready(QImage(*size, QImage.Format_RGB32), tmp_path / f"{name}.png")


def test_one_chip_per_detected_monitor(window):
    assert [(c.name_text(), c.is_active()) for c in window.monitor_chips] == [
        ("DELL U2719", False), ("LG 34WN", False),
    ]
    assert window.monitor_bar.count() == 2


def test_chips_are_disabled_until_a_render_is_ready(window, tmp_path, submitted):
    assert not any(chip.isEnabled() for chip in window.monitor_chips)
    window._on_generate()
    show_render(window, tmp_path)
    assert all(chip.isEnabled() for chip in window.monitor_chips)
    window._on_generate()
    assert not any(chip.isEnabled() for chip in window.monitor_chips)


def test_chip_lights_when_the_render_fits_that_monitor(window, tmp_path, submitted):
    window._on_generate()
    show_render(window, tmp_path, (3440, 1440))
    assert [chip.is_active() for chip in window.monitor_chips] == [False, True]


def test_no_monitors_means_no_chips(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(main_window, "detect_monitors", lambda screens: [])
    win = MainWindow(preview_max_width=160, render_directory=tmp_path)
    qtbot.addWidget(win)
    assert win.monitor_chips == []
    assert win.set_all_button.text() == "Set on all monitors"


def test_monitor_sizes_are_offered_first_without_changing_the_default(window):
    combo = window.size_combo
    assert combo.itemData(0) == (2560, 1440)
    assert combo.itemText(0) == "DELL U2719 · 2560 x 1440"
    assert combo.itemData(1) == (3440, 1440)
    assert combo.itemData(2) is None  # separator
    assert combo.currentData() == "1440p"
    assert window.current_spec() == RenderSpec(seed=20260813)


def test_picking_a_monitor_size_renders_at_that_size(window):
    window.size_combo.setCurrentIndex(1)
    assert window.current_spec().width == 3440


def test_clicking_a_fitting_monitor_sets_it_immediately(qtbot, window, tmp_path, submitted, set_calls):
    window._on_generate()
    show_render(window, tmp_path)
    qtbot.mouseClick(window.monitor_chips[0], Qt.LeftButton)
    assert set_calls == [(tmp_path / "render.png", DELL.device_path)]
    assert window.render_status.text() == "Wallpaper set on DELL U2719."
    assert len(submitted) == 1  # nothing re-rendered


def test_clicking_another_size_rerenders_the_same_design_then_sets_it(
    qtbot, window, tmp_path, submitted, set_calls
):
    window.palette_combo.setCurrentIndex(window.palette_combo.findData("amber"))
    window.seed_field.set_seed(42)
    window._on_generate()
    show_render(window, tmp_path)
    window.seed_field.set_seed(7)  # an unrendered edit must not leak into the re-render

    qtbot.mouseClick(window.monitor_chips[1], Qt.LeftButton)
    assert submitted[-1] == submitted[0].at(3440, 1440)
    assert (submitted[-1].seed, submitted[-1].palette) == (42, "amber")
    assert window.current_spec() == submitted[-1]  # controls show what is rendering
    assert "3440 × 1440 for LG 34WN" in window.render_status.text()
    assert set_calls == []
    assert not window.set_all_button.isEnabled()

    show_render(window, tmp_path, (3440, 1440), "ultrawide")
    assert set_calls == [(tmp_path / "ultrawide.png", ULTRAWIDE.device_path)]
    assert window.render_status.text() == "Wallpaper set on LG 34WN."
    assert [chip.is_active() for chip in window.monitor_chips] == [False, True]


def test_generating_again_cancels_a_pending_monitor(qtbot, window, tmp_path, submitted, set_calls):
    window._on_generate()
    show_render(window, tmp_path)
    qtbot.mouseClick(window.monitor_chips[1], Qt.LeftButton)
    window._on_generate()
    show_render(window, tmp_path, (3440, 1440), "other")
    assert set_calls == []


def test_a_failed_rerender_cancels_a_pending_monitor(qtbot, window, tmp_path, submitted, set_calls):
    window._on_generate()
    show_render(window, tmp_path)
    qtbot.mouseClick(window.monitor_chips[1], Qt.LeftButton)
    window._on_failed("out of memory")
    window._on_generate()
    show_render(window, tmp_path, (3440, 1440), "later")
    assert set_calls == []


def test_setting_a_monitor_reports_errors_and_allows_retry(qtbot, window, tmp_path, submitted, monkeypatch):
    def fail(path, monitor_id):
        raise OSError("Windows could not set the wallpaper: access denied")

    monkeypatch.setattr(main_window, "set_on_monitor", fail)
    window._on_generate()
    show_render(window, tmp_path)
    qtbot.mouseClick(window.monitor_chips[0], Qt.LeftButton)
    assert "access denied" in window.render_status.text()
    assert window.monitor_chips[0].isEnabled()


def test_setting_a_monitor_marks_the_library_item(qtbot, window, set_calls):
    spec = RenderSpec(style="terminal", width=2560, height=1440, seed=3)
    path = window.library.save(Image.new("RGB", (2560, 1440)), spec)
    window._requested_spec = spec
    window._on_full_ready(QImage(2560, 1440, QImage.Format_RGB32), path)
    qtbot.mouseClick(window.monitor_chips[0], Qt.LeftButton)
    assert window.library.get(path.stem).last_set_at is not None


def test_refresh_rebuilds_chips_and_sizes_when_monitors_change(window, detected, tmp_path, submitted, set_calls):
    window.size_combo.setCurrentIndex(0)  # DELL size, which is also a preset
    window._on_generate()
    show_render(window, tmp_path)
    window._on_monitor_clicked(ULTRAWIDE)  # pending a render for the ultrawide

    detected.remove(ULTRAWIDE)  # unplugged mid-render
    window.refresh_monitors()
    assert [chip.name_text() for chip in window.monitor_chips] == ["DELL U2719"]
    assert [window.size_combo.itemData(i) for i in range(2)] == [(2560, 1440), None]
    show_render(window, tmp_path, (3440, 1440), "late")
    assert set_calls == []  # the unplugged monitor is not targeted


def test_refresh_keeps_a_selected_size_that_still_exists(window, detected):
    window.size_combo.setCurrentIndex(window.size_combo.findData("4k"))
    detected.append(Monitor("x", 6000, 0, 1920, 1080, "Side"))
    window.refresh_monitors()
    assert window.size_combo.currentData() == "4k"
    assert len(window.monitor_chips) == 3


def test_screen_changes_trigger_a_debounced_refresh(qtbot, window, monkeypatch):
    calls = []
    monkeypatch.setattr(main_window, "detect_monitors", lambda screens: calls.append(screens) or [DELL])
    window._monitor_timer.setInterval(10)
    window._schedule_monitor_refresh()
    window._schedule_monitor_refresh()
    qtbot.waitUntil(lambda: len(window.monitor_chips) == 1, timeout=2000)
    assert len(calls) == 1


def test_end_to_end_library_item_rerendered_for_a_small_monitor(qtbot, tmp_path, monkeypatch, set_calls):
    tiny = Monitor("tiny", 0, 0, 320, 180, "Tiny")
    monkeypatch.setattr(main_window, "detect_monitors", lambda screens: [tiny])
    win = MainWindow(preview_max_width=160, render_directory=tmp_path)
    qtbot.addWidget(win)
    try:
        spec = RenderSpec(style="terminal", width=640, height=360, seed=11)
        path = win.library.save(Image.new("RGB", (640, 360)), spec)
        win.library_panel.refresh()
        with qtbot.waitSignal(win.controller.full_ready, timeout=10000):
            win._load_library_item(path.stem)
        assert not win.monitor_chips[0].is_active()

        win.monitor_chips[0].clicked.emit()
        qtbot.waitUntil(lambda: bool(set_calls), timeout=20000)
        new_path, monitor_id = set_calls[0]
        assert monitor_id == "tiny"
        assert new_path != path
        entry = win.library.get(new_path.stem)
        assert entry.spec == spec.at(320, 180)
        assert entry.last_set_at is not None
        assert win.monitor_chips[0].is_active()
    finally:
        win.controller.wait_for_done()
