from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QColor, QImage

from wallgen.ui.preview_pane import PreviewPane, fit_rect


def _image(width: int = 40, height: int = 20, color: str = "#336699") -> QImage:
    image = QImage(width, height, QImage.Format_RGB888)
    image.fill(QColor(color))
    return image


def test_fit_rect_letterboxes_a_wide_source_vertically():
    assert fit_rect(200, 100, QRect(0, 0, 100, 100)) == QRect(0, 25, 100, 50)


def test_fit_rect_pillarboxes_a_tall_source_horizontally():
    assert fit_rect(100, 200, QRect(0, 0, 100, 100)) == QRect(25, 0, 50, 100)


def test_fit_rect_fills_when_aspect_matches():
    assert fit_rect(160, 90, QRect(10, 20, 320, 180)) == QRect(10, 20, 320, 180)


def test_fit_rect_returns_a_null_rect_for_degenerate_input():
    assert fit_rect(0, 100, QRect(0, 0, 100, 100)).isNull()
    assert fit_rect(100, 100, QRect(0, 0, 0, 0)).isNull()


def test_pane_starts_empty(qtbot):
    pane = PreviewPane()
    qtbot.addWidget(pane)
    assert pane.has_image() is False
    assert pane.error_text() == ""


def test_show_image_sets_the_pixmap_and_the_fade_finishes(qtbot):
    pane = PreviewPane(fade_ms=50)
    qtbot.addWidget(pane)
    pane.show_image(_image(40, 20))
    assert pane.has_image() is True
    assert pane.image_size() == QSize(40, 20)
    qtbot.waitUntil(lambda: not pane.is_fading(), timeout=2000)


def test_second_image_replaces_the_first(qtbot):
    pane = PreviewPane(fade_ms=50)
    qtbot.addWidget(pane)
    pane.show_image(_image(40, 20))
    pane.show_image(_image(60, 30))
    assert pane.image_size() == QSize(60, 30)
    qtbot.waitUntil(lambda: not pane.is_fading(), timeout=2000)


def test_error_keeps_the_last_image_and_a_new_image_clears_it(qtbot):
    pane = PreviewPane(fade_ms=50)
    qtbot.addWidget(pane)
    pane.show_image(_image())
    pane.show_error("boom")
    assert pane.has_image() is True
    assert pane.error_text() == "boom"
    pane.show_image(_image())
    assert pane.error_text() == ""


def test_each_state_paints_differently(qtbot):
    pane = PreviewPane(fade_ms=50)
    qtbot.addWidget(pane)
    pane.resize(240, 140)
    empty = pane.grab().toImage()  # "Press Generate" hint
    pane.show_image(_image())
    qtbot.waitUntil(lambda: not pane.is_fading(), timeout=2000)
    with_image = pane.grab().toImage()
    pane.show_error("a fairly long error message " * 6)  # exercises eliding too
    with_error = pane.grab().toImage()
    assert with_image != empty
    assert with_error != with_image
