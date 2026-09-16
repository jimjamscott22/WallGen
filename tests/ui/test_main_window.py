from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame

from wallgen.ui import theme
from wallgen.ui.main_window import MainWindow
from wallgen.ui.mock_data import MOCK_LIBRARY, MOCK_MONITORS, MOCK_STYLES
from wallgen.ui.style_options import STYLE_LABELS


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


def test_control_rail_has_expected_combo_options(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert [window.style_combo.itemText(i) for i in range(window.style_combo.count())] == [
        STYLE_LABELS[s] for s in MOCK_STYLES
    ]
    assert window.seed_field.seed() == 20260813


def test_monitor_chips_match_mock_data(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert len(window.monitor_chips) == len(MOCK_MONITORS)
    assert window.monitor_chips[0].name_text() == "All"
    assert window.monitor_chips[0].is_active() is True


def test_library_strip_matches_mock_data(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert len(window.library_thumbnails) == len(MOCK_LIBRARY)


def test_window_opens_on_the_style_its_combo_shows(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.style_panel.current_style_label() == f"{window.style_combo.currentText()} options"


def test_changing_style_combo_swaps_the_panel(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.style_combo.setCurrentIndex(MOCK_STYLES.index("terminal"))
    assert window.style_panel.current_style_label() == "Terminal options"


def test_reroll_dial_changes_the_seed(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    original_seed = window.seed_field.seed()
    qtbot.mouseClick(window.reroll_dial, Qt.LeftButton)
    assert window.seed_field.seed() != original_seed


def test_control_rail_vertical_dividers_are_not_height_clamped(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    vertical_dividers = [
        frame
        for frame in window.findChildren(QFrame)
        if frame.property("role") == "hairline-v"
    ]
    assert len(vertical_dividers) == 3
    for divider in vertical_dividers:
        assert divider.maximumHeight() >= 30
