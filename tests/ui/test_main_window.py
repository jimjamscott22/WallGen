import pytest
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QFrame

from wallgen.engine import PALETTES, SIZES, EngineError, RenderSpec
from wallgen.ui import jobs, theme
from wallgen.ui import main_window
from wallgen.ui.main_window import QUIET_ZONES, MainWindow
from wallgen.ui.style_options import STYLE_LABELS, STYLE_ORDER

TINY = 320  # preview width used by tests that really render


@pytest.fixture
def window(qtbot, tmp_path):
    win = MainWindow(preview_max_width=TINY, render_directory=tmp_path)
    qtbot.addWidget(win)
    yield win
    win.controller.wait_for_done()


def _combo_data(combo):
    return [combo.itemData(i) for i in range(combo.count())]


def test_window_title_and_size(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.windowTitle() == "WallGen"
    assert window.size().width() == 1440
    assert window.size().height() == 900


def test_window_applies_theme_stylesheet(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert theme.COPPER in window.styleSheet()


def test_control_rail_combos_are_fed_from_the_engine(window):
    assert _combo_data(window.style_combo) == STYLE_ORDER
    assert [window.style_combo.itemText(i) for i in range(window.style_combo.count())] == [
        STYLE_LABELS[s] for s in STYLE_ORDER
    ]
    assert _combo_data(window.palette_combo) == list(PALETTES)
    assert _combo_data(window.size_combo) == list(SIZES)
    assert _combo_data(window.quiet_combo) == list(QUIET_ZONES)
    assert window.seed_field.seed() == 20260813


def test_window_defaults_build_the_default_spec(window):
    assert window.current_spec() == RenderSpec(seed=20260813)


def test_current_spec_reflects_the_controls(window):
    window.style_combo.setCurrentIndex(window.style_combo.findData("terminal"))
    window.palette_combo.setCurrentIndex(window.palette_combo.findData("amber"))
    window.size_combo.setCurrentIndex(window.size_combo.findData("uw-1440"))
    window.quiet_combo.setCurrentIndex(window.quiet_combo.findData("none"))
    window.seed_field.set_seed(777)
    window.style_panel.editor("user").setText("jamie@box")

    spec = window.current_spec()
    assert (spec.style, spec.palette, spec.quiet_zone, spec.seed) == ("terminal", "amber", "none", 777)
    assert (spec.width, spec.height) == (3440, 1440)
    assert spec.user == "jamie@box"


def test_set_all_starts_disabled(window):
    assert window.set_all_button.text() == "Set on all monitors"
    assert not window.set_all_button.isEnabled()


def test_library_starts_empty(window):
    assert window.library_panel.grid.count() == 0
    assert "start your library" in window.library_panel.hint.text()


def test_window_opens_on_the_style_its_combo_shows(window):
    assert window.style_panel.current_style_label() == f"{window.style_combo.currentText()} options"


def test_changing_style_combo_swaps_the_panel(window):
    window.style_combo.setCurrentIndex(STYLE_ORDER.index("terminal"))
    assert window.style_panel.current_style_label() == "Terminal options"


def test_generate_renders_and_shows_a_preview(qtbot, window):
    assert window.preview_pane.has_image() is False
    window.style_combo.setCurrentIndex(window.style_combo.findData("terminal"))
    qtbot.mouseClick(window.generate_button, Qt.LeftButton)
    qtbot.waitUntil(window.preview_pane.has_image, timeout=15000)
    assert window.preview_pane.image_size() == QSize(320, 180)
    qtbot.waitUntil(window.set_all_button.isEnabled, timeout=20000)
    assert window.preview_pane.image_size() == QSize(2560, 1440)
    assert window.progress_track.fraction() == 1.0


def test_changing_a_control_does_not_render(qtbot, window):
    window.palette_combo.setCurrentIndex(window.palette_combo.findData("ice"))
    window.seed_field.set_seed(5)
    qtbot.wait(200)
    assert window.preview_pane.has_image() is False


def test_reroll_changes_the_seed_and_submits_that_spec(qtbot, window, monkeypatch):
    submitted = []
    monkeypatch.setattr(window.controller, "submit", submitted.append)
    original_seed = window.seed_field.seed()
    qtbot.mouseClick(window.reroll_dial, Qt.LeftButton)
    assert window.seed_field.seed() != original_seed
    assert len(submitted) == 1
    assert submitted[0].seed == window.seed_field.seed()


def test_a_failed_render_shows_the_error_and_keeps_running(qtbot, window, monkeypatch):
    def boom(spec, max_width, progress=None):
        raise EngineError("kaboom")

    monkeypatch.setattr(jobs, "preview", boom)
    qtbot.mouseClick(window.generate_button, Qt.LeftButton)
    qtbot.waitUntil(lambda: window.preview_pane.error_text() == "kaboom", timeout=5000)
    assert window.preview_pane.has_image() is False


def test_control_rail_vertical_dividers_are_not_height_clamped(window):
    vertical_dividers = [
        frame
        for frame in window.findChildren(QFrame)
        if frame.property("role") == "hairline-v"
    ]
    assert len(vertical_dividers) == 3
    for divider in vertical_dividers:
        assert divider.maximumHeight() >= 30


def test_set_all_uses_displayed_render_even_if_controls_change(window, monkeypatch, tmp_path):
    from PySide6.QtGui import QImage

    saved = tmp_path / "render.png"
    image = QImage(640, 360, QImage.Format_RGB32)
    window._on_full_ready(image, saved)
    window.seed_field.set_seed(999)
    calls = []
    monkeypatch.setattr(main_window, "set_on_all_monitors", calls.append)
    window.set_all_button.click()
    assert calls == [saved]
    assert window.render_status.text() == "Wallpaper set on all monitors."
    monkeypatch.setattr(window.controller, "submit", lambda spec: None)
    window._on_generate()
    assert not window.set_all_button.isEnabled()
    window._on_set_all()
    assert calls == [saved]


def test_set_failure_shows_error_and_allows_retry(window, monkeypatch, tmp_path):
    from PySide6.QtGui import QImage

    window._on_full_ready(QImage(10, 10, QImage.Format_RGB32), tmp_path / "render.png")

    def fail(path):
        raise OSError("access denied")

    monkeypatch.setattr(main_window, "set_on_all_monitors", fail)
    window.set_all_button.click()
    assert "access denied" in window.render_status.text()
    assert window.set_all_button.isEnabled()
