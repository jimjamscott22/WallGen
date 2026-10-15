from dataclasses import replace

from PIL import Image
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QMessageBox
import pytest

from wallgen.engine import RenderSpec, SIZES
from wallgen.ui import jobs
from wallgen.ui.main_window import MainWindow


@pytest.fixture
def window(qtbot, tmp_path):
    window = MainWindow(preview_max_width=160, render_directory=tmp_path)
    qtbot.addWidget(window)
    yield window
    window.controller.wait_for_done()


def add(window, spec=None):
    spec = spec or RenderSpec(style="terminal", width=640, height=360, seed=9)
    path = window.library.save(Image.new("RGB", (spec.width, spec.height), (10, 20, 30)), spec)
    window.library_panel.refresh()
    return path.stem, spec


def test_double_click_load_restores_all_controls_and_saved_image(qtbot, window):
    spec = RenderSpec(style="codeblock", palette="ice", width=640, height=360, seed=123,
                      quiet_zone="none", user="me@host", code_text="hello", gutter=False,
                      cursor=False, caption="test", mark="hidden PCB text")
    item_id, _ = add(window, spec)
    window.show()
    panel = window.library_panel
    qtbot.wait(50)
    rectangle = panel.grid.visualItemRect(panel.grid.item(0))
    qtbot.mouseClick(panel.grid.viewport(), Qt.LeftButton, pos=rectangle.center())
    with qtbot.waitSignal(window.controller.full_ready, timeout=10000):
        qtbot.mouseDClick(panel.grid.viewport(), Qt.LeftButton, pos=rectangle.center())
    assert window.current_spec() == spec
    assert window.preview_pane.image_size() == QSize(640, 360)
    assert window.set_all_button.isEnabled()
    assert window._render_path == window.library.image_path(item_id)
    assert len(window.library.list()) == 1  # loading does not create a duplicate


def test_filter_and_favorites(qtbot, window):
    first, _ = add(window)
    add(window, RenderSpec(style="pcb", palette="amber", width=640, height=360))
    panel = window.library_panel
    panel.toggle_favorite(first)
    panel.favorites.setChecked(True)
    assert panel.grid.count() == 1
    assert panel.grid.item(0).data(Qt.UserRole) == first
    panel.search.setText("amber")
    qtbot.waitUntil(lambda: panel.grid.count() == 0)
    panel.favorites.setChecked(False)
    assert panel.grid.count() == 1


def test_generate_auto_saves_and_reopening_restores_library(qtbot, window):
    spec = RenderSpec(style="terminal", width=640, height=360)
    window.load_spec(spec)
    with qtbot.waitSignal(window.controller.full_ready, timeout=15000):
        window.generate_button.click()
    assert window.library_panel.grid.count() == 1
    item_id = window.library.list()[0].id
    reopened = MainWindow(render_directory=window.library.root)
    qtbot.addWidget(reopened)
    assert reopened.library_panel.grid.count() == 1
    assert reopened.library.get(item_id).spec == spec


def test_rerender_preserves_settings_and_changes_only_size(window, monkeypatch):
    item_id, spec = add(window)
    submitted = []
    monkeypatch.setattr(window.controller, "submit", submitted.append)
    window._rerender_library_item(item_id, "1080p")
    assert submitted == [spec.at(*SIZES["1080p"])]
    assert not window.set_all_button.isEnabled()


def test_rerender_creates_a_new_record_and_preserves_original(qtbot, window):
    item_id, spec = add(window)
    with qtbot.waitSignal(window.controller.full_ready, timeout=15000):
        window._rerender_library_item(item_id, "1080p")
    assert len(window.library.list()) == 2
    assert window.library.get(item_id).spec == spec
    assert window.library.get(window._render_path.stem).spec == spec.at(1920, 1080)


def test_missing_saved_image_reports_failure_without_enabling_set(qtbot, window):
    item_id, _ = add(window)
    window.library.image_path(item_id).unlink()
    with qtbot.waitSignal(window.controller.failed, timeout=5000):
        window._load_library_item(item_id)
    assert not window.set_all_button.isEnabled()
    assert "failed" in window.render_status.text()


def test_delete_cancel_then_confirm_clears_selection(qtbot, window, monkeypatch):
    item_id, _ = add(window)
    with qtbot.waitSignal(window.controller.full_ready, timeout=5000):
        window._load_library_item(item_id)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    window.library_panel.delete_item(item_id)
    assert window.library_panel.grid.count() == 1
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    window.library_panel.delete_item(item_id)
    assert window.library_panel.grid.count() == 0
    assert not window.set_all_button.isEnabled()
    assert window._render_path is None


def test_load_supersedes_a_pending_render(qtbot, window, monkeypatch):
    from threading import Event

    item_id, spec = add(window)
    started, release = Event(), Event()
    original = jobs.render

    def held(*args, **kwargs):
        started.set()
        assert release.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(jobs, "render", held)
    try:
        window.load_spec(replace(spec, seed=999))
        window._on_generate()
        qtbot.waitUntil(started.is_set, timeout=10000)
        with qtbot.waitSignal(window.controller.full_ready, timeout=5000):
            window._load_library_item(item_id)
    finally:
        release.set()
        window.controller.wait_for_done()
    qtbot.wait(100)
    assert window._render_path == window.library.image_path(item_id)
    assert window.current_spec() == spec
    assert len(window.library.list()) == 2  # stale render is still saved, but not displayed


def test_delete_during_load_prevents_late_result_from_reenabling_set(qtbot, window, monkeypatch):
    from threading import Event

    item_id, _ = add(window)
    started, release = Event(), Event()
    original = jobs.pil_to_qimage

    def held(image):
        started.set()
        assert release.wait(10)
        return original(image)

    monkeypatch.setattr(jobs, "pil_to_qimage", held)
    try:
        window._load_library_item(item_id)
        qtbot.waitUntil(started.is_set, timeout=5000)
        # Simulate a committed deletion notification while decoding is in flight.
        window._on_library_deleted(item_id)
    finally:
        release.set()
        window.controller.wait_for_done()
    qtbot.wait(50)
    assert not window.set_all_button.isEnabled()
    assert window._render_path is None


def test_pagination_loads_older_entries_without_duplicates(window):
    for seed in range(103):
        spec = RenderSpec(width=32, height=18, seed=seed)
        window.library.save(Image.new("RGB", (32, 18)), spec)
    panel = window.library_panel
    panel.refresh()
    assert panel.grid.count() == 100
    assert panel.more.isEnabled()
    panel.more.click()
    assert panel.grid.count() == 103
    assert len({panel.grid.item(i).data(Qt.UserRole) for i in range(103)}) == 103
    assert not panel.more.isEnabled()


def test_open_folder_uses_library_location(window, monkeypatch):
    from PySide6.QtGui import QDesktopServices

    item_id, _ = add(window)
    urls = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: urls.append(url) or True)
    window.library_panel.open_folder(item_id)
    assert urls[0].toLocalFile() == str(window.library.image_dir).replace('\\', '/')


def test_library_query_failure_is_visible_and_does_not_crash(window, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("database unavailable")

    monkeypatch.setattr(window.library, "list", fail)
    window.library_panel.refresh()
    assert "database unavailable" in window.library_panel.hint.text()
