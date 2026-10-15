"""Off-thread preview, full-resolution rendering and PNG saving.

Rendering and disk writes never run on the GUI thread. A `RenderJob` runs
on a `QThreadPool` capped at 2 threads and hands back a preview, then the
full `QImage` and saved path through queued signals. Cancellation is by generation
counter: every `submit()` bumps it, and results tagged with an older
generation are dropped instead of displayed.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QImage

from wallgen.engine import RenderSpec, preview, render
from wallgen.store.paths import save_render
from wallgen.store.db import LibraryStore

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
    preview = Signal(int, QImage)
    finished = Signal(int, QImage, object)
    failed = Signal(int, str)


class RenderJob(QRunnable):
    def __init__(
        self, spec: RenderSpec, generation: int, max_width: int,
        signals: _JobSignals, directory: Path | None = None,
        library: LibraryStore | None = None,
    ):
        super().__init__()
        self._spec = spec
        self._generation = generation
        self._max_width = max_width
        self._signals = signals
        self._directory = directory
        self._library = library

    def run(self) -> None:
        # Nothing may escape run(): an exception in a pool thread would be lost.
        try:
            image = preview(
                self._spec,
                self._max_width,
                progress=lambda fraction, note: self._signals.progress.emit(
                    self._generation, fraction * 0.2, f"Preview: {note}"
                ),
            )
            self._signals.preview.emit(self._generation, pil_to_qimage(image))
            # Reuse the preview when it already has the requested dimensions.
            if image.size != (self._spec.width, self._spec.height):
                image = render(
                    self._spec,
                    progress=lambda fraction, note: self._signals.progress.emit(
                        self._generation, 0.2 + fraction * 0.75, f"Full resolution: {note}"
                    ),
                )
            self._signals.progress.emit(self._generation, 0.95, "Saving full-resolution PNG…")
            path = (self._library.save(image, self._spec) if self._library is not None
                    else save_render(image, self._directory))
            qimage = pil_to_qimage(image)
        except Exception as exc:  # noqa: BLE001 - reported to the UI, not swallowed
            self._signals.failed.emit(self._generation, str(exc) or type(exc).__name__)
            return
        self._signals.finished.emit(self._generation, qimage, path)


class LoadJob(QRunnable):
    """Decode a saved full-resolution image off the GUI thread."""

    def __init__(self, path: Path, generation: int, signals: _JobSignals):
        super().__init__()
        self.path, self.generation, self.signals = path, generation, signals

    def run(self) -> None:
        try:
            with Image.open(self.path) as image:
                result = pil_to_qimage(image)
        except Exception as exc:
            self.signals.failed.emit(self.generation, str(exc) or type(exc).__name__)
            return
        self.signals.finished.emit(self.generation, result, self.path)


class RenderController(QObject):
    """Re-emits only the latest generation's preview and saved full render."""

    preview_ready = Signal(QImage)
    full_ready = Signal(QImage, object)
    library_changed = Signal()
    progress = Signal(float, str)
    failed = Signal(str)
    busy_changed = Signal(bool)

    def __init__(
        self, max_width: int = DEFAULT_PREVIEW_WIDTH, parent: QObject | None = None,
        directory: Path | None = None,
        library: LibraryStore | None = None,
    ):
        super().__init__(parent)
        self._max_width = max_width
        self._directory = directory
        self._library = library
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(_MAX_THREADS)
        self._generation = 0
        self._busy = False
        # Keeps each job's signal object alive until its result has been handled.
        self._live: dict[int, _JobSignals] = {}

    def _start(self) -> tuple[int, _JobSignals]:
        self._generation += 1
        generation = self._generation
        signals = _JobSignals()
        signals.progress.connect(self._on_progress)
        signals.preview.connect(self._on_preview)
        signals.finished.connect(self._on_finished)
        signals.failed.connect(self._on_failed)
        self._live[generation] = signals
        self._set_busy(True)
        return generation, signals

    def submit(self, spec: RenderSpec) -> None:
        generation, signals = self._start()
        self._pool.start(RenderJob(
            spec, generation, self._max_width, signals, self._directory, self._library
        ))

    def load(self, path: Path) -> None:
        generation, signals = self._start()
        self._pool.start(LoadJob(path, generation, signals))

    def invalidate(self) -> None:
        """Prevent pending work from replacing an explicitly cleared selection."""
        self._generation += 1
        self._set_busy(False)

    def wait_for_done(self) -> None:
        self._pool.waitForDone()

    def _set_busy(self, busy: bool) -> None:
        if busy != self._busy:
            self._busy = busy
            self.busy_changed.emit(busy)

    def _on_progress(self, generation: int, fraction: float, note: str) -> None:
        if generation == self._generation:
            self.progress.emit(fraction, note)

    def _on_preview(self, generation: int, image: QImage) -> None:
        if generation == self._generation:
            self.preview_ready.emit(image)

    def _on_finished(self, generation: int, image: QImage, path: Path) -> None:
        self._live.pop(generation, None)
        self.library_changed.emit()
        if generation != self._generation:
            return
        self._set_busy(False)
        self.progress.emit(1.0, "Full-resolution render saved")
        self.full_ready.emit(image, path)

    def _on_failed(self, generation: int, message: str) -> None:
        self._live.pop(generation, None)
        if generation != self._generation:
            return
        self._set_busy(False)
        self.failed.emit(message)
