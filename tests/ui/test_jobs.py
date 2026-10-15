import pytest
from PIL import Image
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from wallgen.engine import EngineError, RenderSpec, preview
from wallgen.ui import jobs
from wallgen.ui.jobs import RenderController, pil_to_qimage

TINY = 320  # a 2560x1440 spec previews as 320x180 — fast enough for tests


@pytest.fixture
def controller(qtbot, tmp_path):
    ctrl = RenderController(max_width=TINY, directory=tmp_path)
    yield ctrl
    ctrl.wait_for_done()


def test_pil_to_qimage_preserves_size_and_pixels():
    qimage = pil_to_qimage(Image.new("RGB", (4, 3), (10, 20, 30)))
    assert qimage.size() == QSize(4, 3)
    color = qimage.pixelColor(2, 1)
    assert (color.red(), color.green(), color.blue()) == (10, 20, 30)


def test_submit_delivers_a_preview_qimage(qtbot, controller):
    spec = RenderSpec(style="terminal", width=640, height=360, seed=3)
    with qtbot.waitSignal(controller.preview_ready, timeout=15000) as blocker:
        controller.submit(spec)
    image = blocker.args[0]
    assert isinstance(image, QImage)
    assert image.size() == QSize(320, 180)
    assert image == pil_to_qimage(preview(spec, TINY))


def test_only_the_latest_submission_is_delivered(qtbot, controller):
    first = RenderSpec(style="pcb", width=640, height=360, seed=1)
    second = RenderSpec(style="pcb", width=640, height=360, seed=2)
    # Guard: the test is only meaningful if the two seeds really differ.
    assert pil_to_qimage(preview(first, TINY)) != pil_to_qimage(preview(second, TINY))

    received = []
    controller.preview_ready.connect(received.append)
    controller.submit(first)
    with qtbot.waitSignal(controller.preview_ready, timeout=15000):
        controller.submit(second)
    controller.wait_for_done()
    qtbot.wait(100)  # let any stale queued result arrive (and be dropped)

    assert len(received) == 1
    assert received[0] == pil_to_qimage(preview(second, TINY))


def test_engine_failure_is_reported_not_raised(qtbot, controller, monkeypatch):
    def boom(spec, max_width, progress=None):
        raise EngineError("boom")

    monkeypatch.setattr(jobs, "preview", boom)
    with qtbot.waitSignal(controller.failed, timeout=5000) as blocker:
        controller.submit(RenderSpec())
    assert blocker.args == ["boom"]


def test_busy_changed_brackets_a_render(qtbot, controller):
    states = []
    controller.busy_changed.connect(states.append)
    with qtbot.waitSignal(controller.full_ready, timeout=15000):
        controller.submit(RenderSpec(style="terminal", width=640, height=360))
    assert states == [True, False]


def test_progress_is_forwarded_and_ends_at_one(qtbot, controller):
    fractions = []
    controller.progress.connect(lambda fraction, note: fractions.append(fraction))
    with qtbot.waitSignal(controller.full_ready, timeout=15000):
        controller.submit(RenderSpec(style="terminal", width=640, height=360))
    assert fractions
    assert fractions[-1] == 1.0


def test_full_render_matches_spec_and_saved_png(qtbot, controller):
    spec = RenderSpec(style="terminal", width=640, height=360, seed=9)
    previews = []
    controller.preview_ready.connect(previews.append)
    with qtbot.waitSignal(controller.full_ready, timeout=15000) as result:
        controller.submit(spec)
    image, path = result.args
    assert previews[0].size() == QSize(320, 180)
    assert image.size() == QSize(640, 360)
    with Image.open(path) as saved:
        assert saved.size == (640, 360)
        assert pil_to_qimage(saved) == image
    assert image == pil_to_qimage(jobs.render(spec))


def test_stale_full_results_progress_and_errors_are_dropped(qtbot, controller):
    from threading import Event

    entered, release = Event(), Event()
    original = jobs.render

    def delayed(spec, progress=None):
        if spec.seed == 1:
            entered.set()
            assert release.wait(10)
        return original(spec, progress)

    # Hold the first full render until the second has been saved and delivered.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(jobs, "render", delayed)
        received, errors, progress = [], [], []
        controller.full_ready.connect(lambda image, path: received.append(path))
        controller.failed.connect(errors.append)
        controller.progress.connect(lambda fraction, note: progress.append(note))
        try:
            controller.submit(RenderSpec(style="terminal", width=640, height=360, seed=1))
            qtbot.waitUntil(entered.is_set, timeout=10000)
            with qtbot.waitSignal(controller.full_ready, timeout=15000):
                controller.submit(RenderSpec(style="terminal", width=640, height=360, seed=2))
            controller._on_failed(1, "stale error")
            controller._on_progress(1, 0.3, "stale progress")
        finally:
            release.set()
            controller.wait_for_done()
        qtbot.wait(100)
        assert len(received) == 1
        assert not errors
        assert "stale progress" not in progress


def test_full_failure_keeps_preview_but_never_reports_ready(qtbot, controller, monkeypatch):
    def boom(*args, **kwargs):
        raise EngineError("full render failed")

    monkeypatch.setattr(jobs, "render", boom)
    previews, full = [], []
    controller.preview_ready.connect(previews.append)
    controller.full_ready.connect(lambda *args: full.append(args))
    with qtbot.waitSignal(controller.failed, timeout=10000) as error:
        controller.submit(RenderSpec(style="terminal", width=640, height=360))
    assert error.args == ["full render failed"]
    assert len(previews) == 1
    assert not full


def test_save_failure_is_reported(qtbot, controller, monkeypatch):
    def boom(*args):
        raise OSError("disk full")

    monkeypatch.setattr(jobs, "save_render", boom)
    with qtbot.waitSignal(controller.failed, timeout=10000) as error:
        controller.submit(RenderSpec(style="terminal", width=320, height=180))
    assert error.args == ["disk full"]


def test_full_render_and_save_stay_off_gui_thread(qtbot, controller, monkeypatch):
    from threading import get_ident

    gui_thread = get_ident()
    threads = []
    original_render, original_save = jobs.render, jobs.save_render

    def tracked_render(*args, **kwargs):
        threads.append(get_ident())
        return original_render(*args, **kwargs)

    def tracked_save(*args):
        threads.append(get_ident())
        return original_save(*args)

    monkeypatch.setattr(jobs, "render", tracked_render)
    monkeypatch.setattr(jobs, "save_render", tracked_save)
    with qtbot.waitSignal(controller.full_ready, timeout=15000):
        controller.submit(RenderSpec(style="terminal", width=640, height=360))
    assert len(threads) == 2
    assert all(thread != gui_thread for thread in threads)
