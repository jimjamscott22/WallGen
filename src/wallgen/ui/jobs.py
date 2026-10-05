"""Off-thread preview rendering for the GUI (spec §6, Threading).

`engine.preview` never runs on the GUI thread. A `RenderJob` runs on a
`QThreadPool` capped at 2 threads and hands back a `QImage` (thread-safe,
unlike `QPixmap`) through queued signals. Cancellation is by generation
counter: every `submit()` bumps it, and results tagged with an older
generation are dropped instead of displayed.
"""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QImage

from wallgen.engine import RenderSpec, preview

DEFAULT_PREVIEW_WIDTH = 1280
_MAX_THREADS = 2


def pil_to_qimage(image: Image.Image) -> QImage:
    """RGB PIL image -> QImage that owns its pixel buffer.

    Avoids PIL.ImageQt, which is fragile across Pillow/PySide versions.
    `.copy()` detaches the QImage from the temporary `bytes` object.
    """
    rgb = image.convert("RGB")
    data = rgb.tobytes()
    qimage = QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format_RGB888)
    return qimage.copy()


class _JobSignals(QObject):
    progress = Signal(int, float, str)
    finished = Signal(int, QImage)
    failed = Signal(int, str)


class RenderJob(QRunnable):
    def __init__(self, spec: RenderSpec, generation: int, max_width: int, signals: _JobSignals):
        super().__init__()
        self._spec = spec
        self._generation = generation
        self._max_width = max_width
        self._signals = signals

    def run(self) -> None:
        # Nothing may escape run(): an exception in a pool thread would be lost.
        try:
            image = preview(
                self._spec,
                self._max_width,
                progress=lambda fraction, note: self._signals.progress.emit(
                    self._generation, fraction, note
                ),
            )
            qimage = pil_to_qimage(image)
        except Exception as exc:  # noqa: BLE001 - reported to the UI, not swallowed
            self._signals.failed.emit(self._generation, str(exc) or type(exc).__name__)
            return
        self._signals.finished.emit(self._generation, qimage)


class RenderController(QObject):
    """Submits preview renders and re-emits only the latest generation's results."""

    preview_ready = Signal(QImage)
    progress = Signal(float, str)
    failed = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, max_width: int = DEFAULT_PREVIEW_WIDTH, parent: QObject | None = None):
        super().__init__(parent)
        self._max_width = max_width
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(_MAX_THREADS)
        self._generation = 0
        self._busy = False
        # Keeps each job's signal object alive until its result has been handled.
        self._live: dict[int, _JobSignals] = {}

    def submit(self, spec: RenderSpec) -> None:
        self._generation += 1
        generation = self._generation
        signals = _JobSignals()
        signals.progress.connect(self._on_progress)
        signals.finished.connect(self._on_finished)
        signals.failed.connect(self._on_failed)
        self._live[generation] = signals
        self._set_busy(True)
        self._pool.start(RenderJob(spec, generation, self._max_width, signals))

    def wait_for_done(self) -> None:
        self._pool.waitForDone()

    def _set_busy(self, busy: bool) -> None:
        if busy != self._busy:
            self._busy = busy
            self.busy_changed.emit(busy)

    def _on_progress(self, generation: int, fraction: float, note: str) -> None:
        if generation == self._generation:
            self.progress.emit(fraction, note)

    def _on_finished(self, generation: int, image: QImage) -> None:
        self._live.pop(generation, None)
        if generation != self._generation:
            return
        self._set_busy(False)
        self.preview_ready.emit(image)

    def _on_failed(self, generation: int, message: str) -> None:
        self._live.pop(generation, None)
        if generation != self._generation:
            return
        self._set_busy(False)
        self.failed.emit(message)
