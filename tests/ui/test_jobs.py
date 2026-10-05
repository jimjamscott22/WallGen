import pytest
from PIL import Image
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from wallgen.engine import EngineError, RenderSpec, preview
from wallgen.ui import jobs
from wallgen.ui.jobs import RenderController, pil_to_qimage

TINY = 320  # a 2560x1440 spec previews as 320x180 — fast enough for tests


@pytest.fixture
def controller(qtbot):
    ctrl = RenderController(max_width=TINY)
    yield ctrl
    ctrl.wait_for_done()


def test_pil_to_qimage_preserves_size_and_pixels():
    qimage = pil_to_qimage(Image.new("RGB", (4, 3), (10, 20, 30)))
    assert qimage.size() == QSize(4, 3)
    color = qimage.pixelColor(2, 1)
    assert (color.red(), color.green(), color.blue()) == (10, 20, 30)


def test_submit_delivers_a_preview_qimage(qtbot, controller):
    spec = RenderSpec(style="terminal", seed=3)
    with qtbot.waitSignal(controller.preview_ready, timeout=15000) as blocker:
        controller.submit(spec)
    image = blocker.args[0]
    assert isinstance(image, QImage)
    assert image.size() == QSize(320, 180)
    assert image == pil_to_qimage(preview(spec, TINY))


def test_only_the_latest_submission_is_delivered(qtbot, controller):
    first = RenderSpec(style="pcb", seed=1)
    second = RenderSpec(style="pcb", seed=2)
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
    with qtbot.waitSignal(controller.preview_ready, timeout=15000):
        controller.submit(RenderSpec(style="terminal"))
    assert states == [True, False]


def test_progress_is_forwarded_and_ends_at_one(qtbot, controller):
    fractions = []
    controller.progress.connect(lambda fraction, note: fractions.append(fraction))
    with qtbot.waitSignal(controller.preview_ready, timeout=15000):
        controller.submit(RenderSpec(style="terminal"))
    assert fractions
    assert fractions[-1] == 1.0
