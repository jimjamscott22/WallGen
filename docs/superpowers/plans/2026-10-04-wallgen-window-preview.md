# WallGen Window With Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task (superpowers:executing-plans and superpowers:test-driven-development are disabled per this user's CLAUDE.md — write the implementation directly, then the test, then run it; skip the red/green ceremony). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the finished engine (`wallgen.engine.preview`) into the existing UI shell so you can change style, palette, size, quiet zone, seed and the style-specific options, press Generate (or ⟳), and see a preview that crossfades in.

**Architecture:** A `RenderController` owns a `QThreadPool` (max 2 threads) and a generation counter. Each Generate submits a `RenderJob` (`QRunnable`) that calls `engine.preview` off the GUI thread and returns a `QImage` through queued signals; results from stale generations are dropped. A new `PreviewPane` widget paints the image aspect-fit and crossfades between images. The right-hand style panel becomes real editors whose values map 1:1 onto `RenderSpec` fields, and the main window builds a `RenderSpec` from its controls.

**Tech Stack:** Python 3.12, PySide6 >= 6.11, Pillow >= 11, pytest + pytest-qt (offscreen platform, already set in `tests/conftest.py`).

**Spec:** [docs/wallgen-spec.md](../../wallgen-spec.md) §6 and §7 Milestone 2, and the approved design: [docs/superpowers/specs/2026-10-04-wallgen-window-preview-design.md](../specs/2026-10-04-wallgen-window-preview-design.md).

## Global Constraints

- Python >= 3.12; package management is `uv` only — `uv run pytest`, never `pip`.
- `engine.render`/`engine.preview` never runs on the GUI thread. Use `QThreadPool` with `maxThreadCount` 2 and cancel-by-generation-counter (stale results are dropped, never displayed).
- Convert PIL image to `QImage` on the worker thread; create `QPixmap` only on the GUI thread (`QPixmap` is not thread-safe).
- Parameter changes do **not** auto-render. Only Generate and ⟳ start a render.
- Do not modify anything under `src/wallgen/engine/`. UI imports engine; engine never imports UI.
- Colors, fonts and radii come from `wallgen.ui.theme` tokens — no new hard-coded hex values in widgets.
- `MOCK_MONITORS` and `MOCK_LIBRARY` stay mocked (Milestones 3–5). `wallpaper.py` at the repo root is left untouched.
- Out of scope: full-size render, saving to disk or library, setting the wallpaper, monitor detection, library load-back.
- Test command for the whole suite: `uv run pytest -q` (run from the repo root, `d:\Code\Python\PythonApps\WallGen`).
- Engine previews at `max_width=320` render in well under 0.1 s per style, so tests use `max_width=320` (a 2560x1440 spec previews as 320x180).

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/wallgen/ui/jobs.py` | Create | `pil_to_qimage`, `RenderJob`, `RenderController` (threading + generation counter) |
| `src/wallgen/ui/preview_pane.py` | Create | `fit_rect`, `PreviewPane` (aspect-fit painting, crossfade, error line, empty hint) |
| `src/wallgen/ui/widgets.py` | Modify | Add `ProgressTrack`; make `SeedField` an editable, validated field |
| `src/wallgen/ui/style_options.py` | Modify | Real, spec-backed editors; `values()` and `editor()` |
| `src/wallgen/ui/theme.py` | Modify | QSS for `QLineEdit`, `QPlainTextEdit`, `QCheckBox` |
| `src/wallgen/ui/main_window.py` | Modify | Engine-fed combos, `current_spec()`, controller wiring, `PreviewPane` + `ProgressTrack` |
| `src/wallgen/ui/mock_data.py` | Modify | Delete the four combo mocks |
| `tests/ui/test_jobs.py` | Create | Controller/job tests against the real engine |
| `tests/ui/test_preview_pane.py` | Create | `fit_rect` and `PreviewPane` tests |
| `tests/ui/test_widgets.py` | Modify | `ProgressTrack` and editable `SeedField` tests |
| `tests/ui/test_style_options.py` | Modify | Editor, `values()`, and style-set consistency tests |
| `tests/ui/test_theme.py` | Modify | Assert new QSS rules exist |
| `tests/ui/test_main_window.py` | Replace | Updated for engine-fed combos and live generation |
| `tests/ui/test_mock_data.py` | Modify | Drop removed constants |

---

### Task 1: `ui/jobs.py` — threaded preview rendering

**Files:**
- Create: `src/wallgen/ui/jobs.py`
- Test: `tests/ui/test_jobs.py`

**Interfaces:**
- Consumes: `wallgen.engine.preview(spec: RenderSpec, max_width: int = 1280, progress: Callable[[float, str], None] | None = None) -> PIL.Image.Image`; `RenderSpec`; `EngineError`.
- Produces (used by Task 5):
  - `DEFAULT_PREVIEW_WIDTH: int` (1280)
  - `pil_to_qimage(image: PIL.Image.Image) -> QImage`
  - `RenderController(max_width: int = DEFAULT_PREVIEW_WIDTH, parent: QObject | None = None)` with
    - `submit(spec: RenderSpec) -> None`
    - `wait_for_done() -> None`
    - signals `preview_ready(QImage)`, `progress(float, str)`, `failed(str)`, `busy_changed(bool)`

- [ ] **Step 1: Write `src/wallgen/ui/jobs.py`**

```python
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
```

- [ ] **Step 2: Write `tests/ui/test_jobs.py`**

```python
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
```

- [ ] **Step 3: Run the tests**

Run: `uv run pytest tests/ui/test_jobs.py -v`
Expected: 6 passed.

- [ ] **Step 4: Commit**

```bash
git add src/wallgen/ui/jobs.py tests/ui/test_jobs.py
git commit -m "feat: add RenderController for off-thread preview rendering"
```

---

### Task 2: `ui/preview_pane.py` — aspect-fit preview with crossfade

**Files:**
- Create: `src/wallgen/ui/preview_pane.py`
- Test: `tests/ui/test_preview_pane.py`

**Interfaces:**
- Consumes: `wallgen.ui.theme` tokens (`BG_VIEWPORT`, `HAIRLINE`, `BG_WINDOW`, `TEXT_MUTED`, `FONT_MONO`).
- Produces (used by Task 5):
  - `fit_rect(src_w: int, src_h: int, dst: QRect) -> QRect`
  - `PreviewPane(fade_ms: int = 200, parent: QWidget | None = None)` with
    - `show_image(image: QImage) -> None`
    - `show_error(message: str) -> None`
    - `has_image() -> bool`, `image_size() -> QSize`, `error_text() -> str`, `is_fading() -> bool`

- [ ] **Step 1: Write `src/wallgen/ui/preview_pane.py`**

```python
"""The preview viewport: paints a QImage aspect-fit and crossfades between images."""

from __future__ import annotations

from PySide6.QtCore import QAbstractAnimation, QRect, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from wallgen.ui import theme

FADE_MS = 200
_ERROR_STRIP_HEIGHT = 28


def fit_rect(src_w: int, src_h: int, dst: QRect) -> QRect:
    """The largest rect with the source's aspect ratio that fits inside `dst`, centered."""
    if src_w <= 0 or src_h <= 0 or dst.width() <= 0 or dst.height() <= 0:
        return QRect()
    scale = min(dst.width() / src_w, dst.height() / src_h)
    width = round(src_w * scale)
    height = round(src_h * scale)
    x = dst.x() + (dst.width() - width) // 2
    y = dst.y() + (dst.height() - height) // 2
    return QRect(x, y, width, height)


class PreviewPane(QWidget):
    def __init__(self, fade_ms: int = FADE_MS, parent: QWidget | None = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._pixmap: QPixmap | None = None
        self._previous: QPixmap | None = None
        self._fade = 1.0
        self._error = ""

        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(fade_ms)
        self._animation.valueChanged.connect(self._on_fade_step)

    # -- public API ---------------------------------------------------------

    def show_image(self, image: QImage) -> None:
        """Fade `image` in over whatever is currently shown. GUI thread only."""
        self._previous = self._pixmap
        self._pixmap = QPixmap.fromImage(image)
        self._error = ""
        self._fade = 0.0
        self._animation.stop()
        self._animation.start()
        self.update()

    def show_error(self, message: str) -> None:
        """Overlay a short error line; the last good image stays visible."""
        self._error = message
        self.update()

    def has_image(self) -> bool:
        return self._pixmap is not None

    def image_size(self) -> QSize:
        return self._pixmap.size() if self._pixmap is not None else QSize()

    def error_text(self) -> str:
        return self._error

    def is_fading(self) -> bool:
        return self._animation.state() == QAbstractAnimation.Running

    # -- internals ----------------------------------------------------------

    def _on_fade_step(self, value) -> None:
        self._fade = float(value)
        if self._fade >= 1.0:
            self._previous = None
        self.update()

    def _draw_pixmap(self, painter: QPainter, pixmap: QPixmap, inner: QRect) -> None:
        target = fit_rect(pixmap.width(), pixmap.height(), inner)
        painter.drawPixmap(target, pixmap)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor(theme.HAIRLINE), 1))
        painter.setBrush(QColor(theme.BG_VIEWPORT))
        painter.drawRoundedRect(frame, 4, 4)

        inner = self.rect().adjusted(1, 1, -1, -1)
        if self._pixmap is None:
            painter.setPen(QColor(theme.TEXT_MUTED))
            painter.drawText(inner, Qt.AlignCenter, "Press Generate")
        else:
            if self._previous is not None:
                self._draw_pixmap(painter, self._previous, inner)
            painter.setOpacity(self._fade)
            self._draw_pixmap(painter, self._pixmap, inner)
            painter.setOpacity(1.0)

        if self._error:
            strip = QRect(inner.left(), inner.bottom() - _ERROR_STRIP_HEIGHT + 1, inner.width(), _ERROR_STRIP_HEIGHT)
            painter.fillRect(strip, QColor(theme.BG_WINDOW))
            font = QFont()
            font.setFamilies(["JetBrains Mono", "Consolas"])
            font.setPixelSize(12)
            painter.setFont(font)
            painter.setPen(QColor(theme.TEXT_MUTED))
            text_rect = strip.adjusted(10, 0, -10, 0)
            elided = painter.fontMetrics().elidedText(self._error, Qt.ElideRight, text_rect.width())
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)
        painter.end()
```

- [ ] **Step 2: Write `tests/ui/test_preview_pane.py`**

```python
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
```

- [ ] **Step 3: Run the tests**

Run: `uv run pytest tests/ui/test_preview_pane.py -v`
Expected: 9 passed.

- [ ] **Step 4: Commit**

```bash
git add src/wallgen/ui/preview_pane.py tests/ui/test_preview_pane.py
git commit -m "feat: add PreviewPane with aspect-fit painting and crossfade"
```

---

### Task 3: `ui/widgets.py` — `ProgressTrack` and an editable `SeedField`

**Files:**
- Modify: `src/wallgen/ui/widgets.py` (imports at lines 3–13; `SeedField` at lines 48–66; add `ProgressTrack` at end of file)
- Test: `tests/ui/test_widgets.py`

**Interfaces:**
- Consumes: `wallgen.ui.theme` tokens.
- Produces (used by Task 5):
  - `ProgressTrack()` with `set_fraction(fraction: float) -> None` (clamped to 0–1; 0 hides the fill) and `fraction() -> float`
  - `SeedField(seed: int = 0, parent=None)` — same `seed() -> int` / `set_seed(seed: int) -> None` API as before, but now an editable digits-only field (0 to 2**31 − 1). An empty field reads as 0.

- [ ] **Step 1: Update the imports at the top of `src/wallgen/ui/widgets.py`**

Replace:

```python
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
```

with:

```python
from PySide6.QtGui import QBrush, QColor, QIntValidator, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)
```

- [ ] **Step 2: Replace the `SeedField` class**

Replace the whole `SeedField` class (from `class SeedField(QFrame):` through its `set_seed` method) with:

```python
MAX_SEED = 2**31 - 1


class SeedField(QFrame):
    """A recessed, monospace, digits-only field for the render seed."""

    def __init__(self, seed: int = 0, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("seedField")
        self.setFixedWidth(150)
        self.setStyleSheet(
            f"QFrame#seedField {{ background: {theme.BG_SEED}; border: 1px solid {theme.HAIRLINE};"
            f" border-radius: 3px; }}"
            f"QFrame#seedField QLineEdit {{ background: transparent; border: none; padding: 0;"
            f" color: {theme.TEXT_PRIMARY}; font-family: {theme.FONT_MONO}; font-size: 14px; }}"
        )
        self._edit = QLineEdit(str(seed))
        self._edit.setValidator(QIntValidator(0, MAX_SEED, self._edit))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.addWidget(self._edit)

    def seed(self) -> int:
        return int(self._edit.text() or 0)

    def set_seed(self, seed: int) -> None:
        self._edit.setText(str(seed))
```

- [ ] **Step 3: Add `ProgressTrack` at the end of `src/wallgen/ui/widgets.py`**

```python
class ProgressTrack(QFrame):
    """The thin track under the preview; a copper fill shows render progress."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(3)
        self._fraction = 0.0

    def fraction(self) -> float:
        return self._fraction

    def set_fraction(self, fraction: float) -> None:
        self._fraction = max(0.0, min(1.0, fraction))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        rect = QRectF(self.rect())
        painter.setBrush(QColor(theme.HAIRLINE))
        painter.drawRoundedRect(rect, 2, 2)
        if self._fraction > 0.0:
            fill = QRectF(rect.left(), rect.top(), rect.width() * self._fraction, rect.height())
            painter.setBrush(QColor(theme.COPPER))
            painter.drawRoundedRect(fill, 2, 2)
        painter.end()
```

- [ ] **Step 4: Update `tests/ui/test_widgets.py`**

Change the import line at the top:

```python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit

from wallgen.ui.widgets import (
    LibraryThumbnail,
    MonitorChip,
    ProgressTrack,
    RerollDial,
    SeedField,
    StatusDot,
)
```

and append these tests at the end of the file:

```python
def test_seed_field_only_accepts_digits(qtbot):
    field = SeedField(5)
    qtbot.addWidget(field)
    edit = field.findChild(QLineEdit)
    edit.clear()
    qtbot.keyClicks(edit, "12ab3")
    assert field.seed() == 123


def test_seed_field_stays_within_the_32_bit_range(qtbot):
    field = SeedField(5)
    qtbot.addWidget(field)
    edit = field.findChild(QLineEdit)
    edit.clear()
    qtbot.keyClicks(edit, "99999999999")
    assert field.seed() <= 2**31 - 1


def test_seed_field_reads_empty_as_zero(qtbot):
    field = SeedField(5)
    qtbot.addWidget(field)
    field.findChild(QLineEdit).clear()
    assert field.seed() == 0


def test_progress_track_clamps_the_fraction(qtbot):
    track = ProgressTrack()
    qtbot.addWidget(track)
    assert track.fraction() == 0.0
    track.set_fraction(0.4)
    assert track.fraction() == 0.4
    track.set_fraction(7)
    assert track.fraction() == 1.0
    track.set_fraction(-3)
    assert track.fraction() == 0.0


def test_progress_track_paints_the_fill(qtbot):
    track = ProgressTrack()
    qtbot.addWidget(track)
    track.resize(200, 3)
    idle = track.grab().toImage()
    track.set_fraction(0.5)
    partial = track.grab().toImage()
    assert partial != idle
```

- [ ] **Step 5: Run the widget tests**

Run: `uv run pytest tests/ui/test_widgets.py tests/ui/test_main_window.py -v`
Expected: all pass (the existing `test_seed_field_round_trip` and `test_control_rail_has_expected_combo_options` still pass against the editable `SeedField`; `test_main_window.py` is not changed until Task 5).

- [ ] **Step 6: Commit**

```bash
git add src/wallgen/ui/widgets.py tests/ui/test_widgets.py
git commit -m "feat: add ProgressTrack and make SeedField an editable validated field"
```

---

### Task 4: `ui/style_options.py` — real, spec-backed editors

**Files:**
- Modify: `src/wallgen/ui/style_options.py` (replace whole file)
- Modify: `src/wallgen/ui/theme.py` (append QSS rules inside `stylesheet()`)
- Test: `tests/ui/test_style_options.py` (replace whole file), `tests/ui/test_theme.py` (append one test)

**Interfaces:**
- Consumes: `RenderSpec` defaults (`wallgen.engine`); `wallgen.engine.spec.Style`.
- Produces (used by Task 5):
  - `STYLE_ORDER: list[str]`, `STYLE_LABELS: dict[str, str]` (unchanged names and values)
  - `StyleOptionsPanel.values() -> dict[str, object]` — keys are exactly the `RenderSpec` field names `mark, submark, chip_label, glyphs, user, title, session_text, code_text, caption, gutter, cursor`; `RenderSpec(**panel.values())` is always valid. Empty text means "engine default" (`user` falls back to `RenderSpec().user`).
  - `StyleOptionsPanel.editor(key: str) -> QWidget`
  - `set_style(style)` and `current_style_label()` unchanged.

- [ ] **Step 1: Replace `src/wallgen/ui/style_options.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from wallgen.engine import RenderSpec

STYLE_ORDER = ["pcb", "coderain", "terminal", "codeblock"]

STYLE_LABELS = {
    "pcb": "PCB",
    "coderain": "Code rain",
    "terminal": "Terminal",
    "codeblock": "Code block",
}

_DEFAULTS = RenderSpec()
_TEXT_BOX_HEIGHT = 120


@dataclass(frozen=True)
class Field:
    """One editor on the panel. `key` is the RenderSpec field it feeds."""

    key: str
    label: str
    kind: Literal["line", "text", "choice", "check"]
    placeholder: str = ""
    choices: tuple[str, ...] = ()
    default: str | bool = ""


# Empty "line"/"text" editors mean "use the engine default": `default` is what
# values() reports for them ("" for most; the engine fills in its own sample).
FIELDS_BY_STYLE: dict[str, list[Field]] = {
    "pcb": [
        Field("mark", "Mark", "line", placeholder="e.g. J A M I E"),
        Field("submark", "Submark", "line", placeholder="e.g. BUILD 2560 x 1440"),
        Field("chip_label", "Chip label", "line", placeholder="e.g. JMI-1440"),
    ],
    "coderain": [
        Field("glyphs", "Glyphs", "choice", choices=("mixed", "ascii"), default=_DEFAULTS.glyphs),
    ],
    "terminal": [
        Field("user", "User", "line", placeholder=_DEFAULTS.user, default=_DEFAULTS.user),
        Field("title", "Window title", "line", placeholder="Default: bash — <user>"),
        Field("session_text", "Session script", "text", placeholder="Empty = built-in demo session"),
    ],
    "codeblock": [
        Field("caption", "Caption", "line", placeholder="Optional line under the code"),
        Field("code_text", "Code", "text", placeholder="Empty = built-in demo snippet"),
        Field("gutter", "Line-number gutter", "check", default=_DEFAULTS.gutter),
        Field("cursor", "Cursor", "check", default=_DEFAULTS.cursor),
    ],
}


def _make_editor(field: Field) -> QWidget:
    if field.kind == "line":
        editor = QLineEdit()
        editor.setPlaceholderText(field.placeholder)
        return editor
    if field.kind == "text":
        editor = QPlainTextEdit()
        editor.setPlaceholderText(field.placeholder)
        editor.setFixedHeight(_TEXT_BOX_HEIGHT)
        return editor
    if field.kind == "choice":
        editor = QComboBox()
        editor.addItems(field.choices)
        editor.setCurrentText(str(field.default))
        return editor
    editor = QCheckBox(field.label)
    editor.setChecked(bool(field.default))
    return editor


def _read(field: Field, editor: QWidget) -> object:
    if field.kind == "line":
        return editor.text() or field.default
    if field.kind == "text":
        return editor.toPlainText() or field.default
    if field.kind == "choice":
        return editor.currentText()
    return editor.isChecked()


def _field_row(field: Field, editor: QWidget) -> QWidget:
    row = QWidget()
    layout = QVBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    if field.kind != "check":  # a checkbox carries its own label
        label = QLabel(field.label)
        label.setProperty("role", "field-label")
        layout.addWidget(label)
    layout.addWidget(editor)
    return row


class StyleOptionsPanel(QFrame):
    """The right-hand panel: editors that swap with the selected style."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("role", "panel")
        self.setFixedWidth(300)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(18)

        self._title = QLabel("")
        self._title.setProperty("role", "value")
        outer.addWidget(self._title)

        self._stack = QStackedWidget()
        outer.addWidget(self._stack)
        outer.addStretch(1)

        self._pages: dict[str, QWidget] = {}
        self._editors: dict[str, tuple[Field, QWidget]] = {}
        for style in STYLE_ORDER:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.setSpacing(16)
            for field in FIELDS_BY_STYLE[style]:
                editor = _make_editor(field)
                self._editors[field.key] = (field, editor)
                page_layout.addWidget(_field_row(field, editor))
            page_layout.addStretch(1)
            self._stack.addWidget(page)
            self._pages[style] = page

        self.set_style(STYLE_ORDER[0])

    def set_style(self, style: str) -> None:
        if style not in self._pages:
            raise ValueError(f"unknown style: {style!r}")
        self._title.setText(f"{STYLE_LABELS[style]} options")
        self._stack.setCurrentWidget(self._pages[style])

    def current_style_label(self) -> str:
        return self._title.text()

    def values(self) -> dict[str, object]:
        """RenderSpec keyword arguments for every style's fields.

        All pages are included so edits survive switching styles; the engine
        ignores fields that belong to other styles.
        """
        return {key: _read(field, editor) for key, (field, editor) in self._editors.items()}

    def editor(self, key: str) -> QWidget:
        return self._editors[key][1]
```

- [ ] **Step 2: Append the new QSS to `stylesheet()` in `src/wallgen/ui/theme.py`**

Inside the f-string returned by `stylesheet()`, add these rules directly before the closing `"""` (after the `QPushButton#generate:hover` rule):

```python
    QLineEdit, QPlainTextEdit {{
        background: {BG_SEED};
        color: {TEXT_PRIMARY};
        font-family: {FONT_MONO};
        font-size: 13px;
        border: 1px solid {HAIRLINE};
        border-radius: 3px;
        padding: 6px 8px;
        selection-background-color: {COPPER};
        selection-color: {BG_WINDOW};
    }}
    QLineEdit:focus, QPlainTextEdit:focus {{
        border: 1px solid {COPPER};
    }}
    QCheckBox {{
        color: {TEXT_PRIMARY};
        font-family: {FONT_UI};
        font-size: 13px;
        spacing: 8px;
    }}
```

- [ ] **Step 3: Append a test to `tests/ui/test_theme.py`**

```python
def test_stylesheet_styles_the_style_panel_editors():
    css = theme.stylesheet()
    assert "QLineEdit, QPlainTextEdit" in css
    assert "QCheckBox" in css
```

- [ ] **Step 4: Replace `tests/ui/test_style_options.py`**

```python
from typing import get_args

import pytest
from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QPlainTextEdit

from wallgen.engine import RenderSpec
from wallgen.engine.spec import Style
from wallgen.ui.style_options import (
    FIELDS_BY_STYLE,
    STYLE_LABELS,
    STYLE_ORDER,
    StyleOptionsPanel,
)

SPEC_KEYS = {
    "mark", "submark", "chip_label",
    "glyphs",
    "user", "title", "session_text",
    "code_text", "caption", "gutter", "cursor",
}


def test_style_order_and_labels_cover_all_four_styles():
    assert STYLE_ORDER == ["pcb", "coderain", "terminal", "codeblock"]
    assert STYLE_LABELS == {
        "pcb": "PCB",
        "coderain": "Code rain",
        "terminal": "Terminal",
        "codeblock": "Code block",
    }


def test_style_order_matches_the_engine_style_set():
    assert set(STYLE_ORDER) == set(get_args(Style))
    assert set(FIELDS_BY_STYLE) == set(STYLE_ORDER)


def test_panel_defaults_to_pcb(qtbot):
    panel = StyleOptionsPanel()
    qtbot.addWidget(panel)
    assert panel.current_style_label() == "PCB options"


@pytest.mark.parametrize("style", STYLE_ORDER)
def test_set_style_switches_the_title(qtbot, style):
    panel = StyleOptionsPanel()
    qtbot.addWidget(panel)
    panel.set_style(style)
    assert panel.current_style_label() == f"{STYLE_LABELS[style]} options"


def test_set_style_rejects_unknown_style(qtbot):
    panel = StyleOptionsPanel()
    qtbot.addWidget(panel)
    with pytest.raises(ValueError):
        panel.set_style("not-a-style")


def test_values_cover_every_spec_field_and_build_the_default_spec(qtbot):
    panel = StyleOptionsPanel()
    qtbot.addWidget(panel)
    values = panel.values()
    assert set(values) == SPEC_KEYS
    assert RenderSpec(**values) == RenderSpec()


def test_editor_kinds(qtbot):
    panel = StyleOptionsPanel()
    qtbot.addWidget(panel)
    assert isinstance(panel.editor("mark"), QLineEdit)
    assert isinstance(panel.editor("glyphs"), QComboBox)
    assert isinstance(panel.editor("session_text"), QPlainTextEdit)
    assert isinstance(panel.editor("gutter"), QCheckBox)


def test_edits_flow_into_values(qtbot):
    panel = StyleOptionsPanel()
    qtbot.addWidget(panel)
    panel.editor("mark").setText("J A M I E")
    panel.editor("glyphs").setCurrentText("ascii")
    panel.editor("code_text").setPlainText("print('hi')")
    panel.editor("gutter").setChecked(False)
    values = panel.values()
    assert values["mark"] == "J A M I E"
    assert values["glyphs"] == "ascii"
    assert values["code_text"] == "print('hi')"
    assert values["gutter"] is False


def test_emptied_user_field_falls_back_to_the_engine_default(qtbot):
    panel = StyleOptionsPanel()
    qtbot.addWidget(panel)
    panel.editor("user").setText("jamie@box")
    assert panel.values()["user"] == "jamie@box"
    panel.editor("user").setText("")
    assert panel.values()["user"] == RenderSpec().user


def test_edits_survive_switching_styles(qtbot):
    panel = StyleOptionsPanel()
    qtbot.addWidget(panel)
    panel.editor("mark").setText("HELLO")
    panel.editor("session_text").setPlainText("$ ls")
    panel.set_style("terminal")
    panel.set_style("pcb")
    values = panel.values()
    assert values["mark"] == "HELLO"
    assert values["session_text"] == "$ ls"
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/ui/test_style_options.py tests/ui/test_theme.py tests/ui/test_widgets.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/wallgen/ui/style_options.py src/wallgen/ui/theme.py tests/ui/test_style_options.py tests/ui/test_theme.py
git commit -m "feat: make the style options panel editable and backed by RenderSpec"
```

---

### Task 5: Wire the main window to the engine, and remove the combo mocks

**Files:**
- Modify: `src/wallgen/ui/main_window.py` (replace whole file)
- Modify: `src/wallgen/ui/mock_data.py` (delete four constants)
- Modify: `tests/ui/test_mock_data.py` (replace whole file)
- Replace: `tests/ui/test_main_window.py`

**Interfaces:**
- Consumes (all produced by Tasks 1–4):
  - `RenderController`, `DEFAULT_PREVIEW_WIDTH` from `wallgen.ui.jobs`
  - `PreviewPane` from `wallgen.ui.preview_pane`
  - `ProgressTrack`, `SeedField` from `wallgen.ui.widgets`
  - `StyleOptionsPanel.values()`, `STYLE_ORDER`, `STYLE_LABELS` from `wallgen.ui.style_options`
  - `PALETTES`, `SIZES`, `RenderSpec` from `wallgen.engine`; `QuietZone` from `wallgen.engine.spec`
- Produces: `MainWindow(preview_max_width: int = DEFAULT_PREVIEW_WIDTH)` with attributes `controller`, `preview_pane`, `progress_track`, `style_combo`, `palette_combo`, `size_combo`, `quiet_combo`, `seed_field`, `reroll_dial`, `generate_button`, `style_panel`, and method `current_spec() -> RenderSpec`.

- [ ] **Step 1: Replace `src/wallgen/ui/main_window.py`**

```python
"""The WallGen main window.

Generate, the reroll dial, the preview pane, the progress track and the style
options are live: they build a RenderSpec and render a preview off-thread via
RenderController. The monitor chips and the library strip are still wired to
mock data (see mock_data.py) until Windows wallpaper-setting and the SQLite
library land in later milestones.
"""

from __future__ import annotations

import random
from typing import get_args

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wallgen.engine import PALETTES, SIZES, RenderSpec
from wallgen.engine.spec import QuietZone
from wallgen.ui import theme
from wallgen.ui.jobs import DEFAULT_PREVIEW_WIDTH, RenderController
from wallgen.ui.mock_data import MOCK_LIBRARY, MOCK_MONITORS
from wallgen.ui.preview_pane import PreviewPane
from wallgen.ui.style_options import STYLE_LABELS, STYLE_ORDER, StyleOptionsPanel
from wallgen.ui.widgets import (
    LibraryThumbnail,
    MonitorChip,
    ProgressTrack,
    RerollDial,
    SeedField,
    StatusDot,
)

QUIET_ZONES = get_args(QuietZone)
DEFAULT_SIZE_KEY = "1440p"
DEFAULT_SEED = 20260813


def _labeled_field(label_text: str, value_widget: QWidget) -> QWidget:
    wrapper = QWidget()
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    label = QLabel(label_text)
    label.setProperty("role", "field-label")
    layout.addWidget(label)
    layout.addWidget(value_widget)
    return wrapper


def _hairline(vertical: bool = False) -> QFrame:
    line = QFrame()
    if vertical:
        # Vertical dividers get their own role: the "hairline" QSS rule
        # clamps max-height/min-height to 1px, which would collapse a
        # vertical divider's setFixedHeight(30) into an invisible dot.
        line.setProperty("role", "hairline-v")
        line.setFixedWidth(1)
        line.setFixedHeight(30)
    else:
        line.setProperty("role", "hairline")
        line.setFixedHeight(1)
    return line


class MainWindow(QMainWindow):
    def __init__(self, preview_max_width: int = DEFAULT_PREVIEW_WIDTH) -> None:
        super().__init__()
        self.setWindowTitle("WallGen")
        self.resize(1440, 900)
        self.setStyleSheet(theme.stylesheet())

        self.controller = RenderController(max_width=preview_max_width, parent=self)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_header())
        root_layout.addWidget(_hairline())
        root_layout.addWidget(self._build_control_rail())
        root_layout.addWidget(_hairline())
        root_layout.addWidget(self._build_main_area(), 1)
        root_layout.addWidget(_hairline())
        root_layout.addWidget(self._build_set_on_row())
        root_layout.addWidget(_hairline())
        root_layout.addWidget(self._build_library_row())

        self._connect_controller()

    def _build_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(28, 16, 28, 16)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        brand.addWidget(StatusDot(theme.VERDIGRIS, glow=True))
        title = QLabel("WallGen")
        title.setStyleSheet(f"font-size: 19px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        brand.addWidget(title)
        subtitle = QLabel("wallpaper generator")
        subtitle.setProperty("role", "field-label")
        brand.addWidget(subtitle)
        layout.addLayout(brand)
        layout.addStretch(1)

        version = QLabel("v0.1")
        version.setProperty("role", "field-label")
        layout.addWidget(version)
        return header

    def _build_control_rail(self) -> QWidget:
        rail = QWidget()
        layout = QHBoxLayout(rail)
        layout.setContentsMargins(28, 14, 28, 14)
        layout.setSpacing(20)

        # Each combo stores the engine key as item data; labels are display only.
        self.style_combo = QComboBox()
        for style in STYLE_ORDER:
            self.style_combo.addItem(STYLE_LABELS[style], style)
        layout.addWidget(_labeled_field("Style", self.style_combo))
        layout.addWidget(_hairline(vertical=True))

        self.palette_combo = QComboBox()
        for key in PALETTES:
            self.palette_combo.addItem(key.capitalize(), key)
        layout.addWidget(_labeled_field("Palette", self.palette_combo))
        layout.addWidget(_hairline(vertical=True))

        self.size_combo = QComboBox()
        for key, (width, height) in SIZES.items():
            self.size_combo.addItem(f"{key} \u00b7 {width} x {height}", key)
        self.size_combo.setCurrentIndex(self.size_combo.findData(DEFAULT_SIZE_KEY))
        layout.addWidget(_labeled_field("Size", self.size_combo))
        layout.addWidget(_hairline(vertical=True))

        self.quiet_combo = QComboBox()
        for zone in QUIET_ZONES:
            self.quiet_combo.addItem(zone.capitalize(), zone)
        layout.addWidget(_labeled_field("Quiet zone", self.quiet_combo))

        layout.addStretch(1)

        self.seed_field = SeedField(DEFAULT_SEED)
        layout.addWidget(_labeled_field("Seed", self.seed_field))

        self.reroll_dial = RerollDial()
        self.reroll_dial.rerolled.connect(self._on_reroll)
        layout.addWidget(self.reroll_dial)

        self.generate_button = QPushButton("Generate")
        self.generate_button.setObjectName("generate")
        self.generate_button.setCursor(Qt.PointingHandCursor)
        self.generate_button.clicked.connect(self._on_generate)
        layout.addWidget(self.generate_button)

        # Connected here (rather than after _build_main_area) relies on
        # _on_style_changed only firing on user interaction, since
        # self.style_panel doesn't exist yet at this point in __init__.
        self.style_combo.currentIndexChanged.connect(self._on_style_changed)
        return rail

    def _build_main_area(self) -> QWidget:
        area = QWidget()
        layout = QHBoxLayout(area)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(20)

        preview_column = QVBoxLayout()
        preview_column.setSpacing(10)

        self.preview_pane = PreviewPane()
        preview_column.addWidget(self.preview_pane, 1)

        self.progress_track = ProgressTrack()
        preview_column.addWidget(self.progress_track)

        preview_widget = QWidget()
        preview_widget.setLayout(preview_column)
        layout.addWidget(preview_widget, 1)

        self.style_panel = StyleOptionsPanel()
        layout.addWidget(self.style_panel)
        return area

    def _build_set_on_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(28, 14, 28, 14)
        layout.setSpacing(14)

        label = QLabel("Set on")
        label.setProperty("role", "field-label")
        layout.addWidget(label)

        self.monitor_chips: list[MonitorChip] = []
        for monitor in MOCK_MONITORS:
            chip = MonitorChip(monitor["name"], monitor["resolution"], monitor["active"])
            self.monitor_chips.append(chip)
            layout.addWidget(chip)

        layout.addStretch(1)
        return row

    def _build_library_row(self) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(28, 14, 28, 18)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Library")
        title.setProperty("role", "field-label")
        header.addWidget(title)
        header.addStretch(1)
        layout.addLayout(header)

        strip = QHBoxLayout()
        strip.setSpacing(12)
        self.library_thumbnails: list[LibraryThumbnail] = []
        for item in MOCK_LIBRARY:
            thumb = LibraryThumbnail(STYLE_LABELS[item["style"]], item["dot"], item["art"])
            self.library_thumbnails.append(thumb)
            strip.addWidget(thumb)
        strip.addStretch(1)
        layout.addLayout(strip)
        return row

    def _connect_controller(self) -> None:
        self.controller.preview_ready.connect(self.preview_pane.show_image)
        self.controller.failed.connect(self.preview_pane.show_error)
        self.controller.progress.connect(self._on_progress)
        self.controller.busy_changed.connect(self._on_busy_changed)

    def current_spec(self) -> RenderSpec:
        width, height = SIZES[self.size_combo.currentData()]
        return RenderSpec(
            style=self.style_combo.currentData(),
            width=width,
            height=height,
            palette=self.palette_combo.currentData(),
            seed=self.seed_field.seed(),
            quiet_zone=self.quiet_combo.currentData(),
            **self.style_panel.values(),
        )

    def _on_generate(self) -> None:
        self.controller.submit(self.current_spec())

    def _on_style_changed(self, index: int) -> None:
        self.style_panel.set_style(self.style_combo.itemData(index))

    def _on_reroll(self) -> None:
        self.seed_field.set_seed(random.randint(0, 99_999_999))
        self._on_generate()

    def _on_progress(self, fraction: float, note: str) -> None:
        self.progress_track.set_fraction(fraction)

    def _on_busy_changed(self, busy: bool) -> None:
        if not busy:
            self.progress_track.set_fraction(0.0)
```

- [ ] **Step 2: Delete the four combo mocks from `src/wallgen/ui/mock_data.py`**

Remove these lines (and the blank lines between them), leaving the docstring, `MOCK_MONITORS` and `MOCK_LIBRARY`:

```python
MOCK_STYLES = ["pcb", "coderain", "terminal", "codeblock"]

MOCK_PALETTES = ["cyber", "amber", "matrix", "violet", "ice", "crimson"]

MOCK_SIZES = ["2560 x 1440", "3440 x 1440", "1920 x 1080"]

MOCK_QUIET_ZONES = ["left", "top", "none"]
```

Also update the module docstring so it no longer claims to stand in for the render engine:

```python
"""Placeholder content standing in for the SQLite library and Windows
monitor detection until those subsystems exist (spec §4, §5)."""
```

- [ ] **Step 3: Replace `tests/ui/test_mock_data.py`**

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from wallgen.ui import mock_data
from wallgen.ui.style_options import STYLE_ORDER


def test_mock_monitors_have_required_shape():
    assert len(mock_data.MOCK_MONITORS) == 3
    for monitor in mock_data.MOCK_MONITORS:
        assert set(monitor) == {"name", "resolution", "active"}
    assert mock_data.MOCK_MONITORS[0]["active"] is True


def test_mock_library_items_reference_known_styles():
    assert len(mock_data.MOCK_LIBRARY) == 6
    for item in mock_data.MOCK_LIBRARY:
        assert set(item) == {"style", "dot", "art"}
        assert item["style"] in STYLE_ORDER


def test_combo_mocks_are_gone():
    for name in ("MOCK_STYLES", "MOCK_PALETTES", "MOCK_SIZES", "MOCK_QUIET_ZONES"):
        assert not hasattr(mock_data, name)
```

- [ ] **Step 4: Replace `tests/ui/test_main_window.py`**

```python
import pytest
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QFrame

from wallgen.engine import PALETTES, SIZES, EngineError, RenderSpec
from wallgen.ui import jobs, theme
from wallgen.ui.main_window import QUIET_ZONES, MainWindow
from wallgen.ui.mock_data import MOCK_LIBRARY, MOCK_MONITORS
from wallgen.ui.style_options import STYLE_LABELS, STYLE_ORDER

TINY = 320  # preview width used by tests that really render


@pytest.fixture
def window(qtbot):
    win = MainWindow(preview_max_width=TINY)
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


def test_monitor_chips_match_mock_data(window):
    assert len(window.monitor_chips) == len(MOCK_MONITORS)
    assert window.monitor_chips[0].name_text() == "All"
    assert window.monitor_chips[0].is_active() is True


def test_library_strip_matches_mock_data(window):
    assert len(window.library_thumbnails) == len(MOCK_LIBRARY)


def test_window_opens_on_the_style_its_combo_shows(window):
    assert window.style_panel.current_style_label() == f"{window.style_combo.currentText()} options"


def test_changing_style_combo_swaps_the_panel(window):
    window.style_combo.setCurrentIndex(STYLE_ORDER.index("terminal"))
    assert window.style_panel.current_style_label() == "Terminal options"


def test_generate_renders_and_shows_a_preview(qtbot, window):
    assert window.preview_pane.has_image() is False
    qtbot.mouseClick(window.generate_button, Qt.LeftButton)
    qtbot.waitUntil(window.preview_pane.has_image, timeout=15000)
    assert window.preview_pane.image_size() == QSize(320, 180)
    qtbot.waitUntil(lambda: window.progress_track.fraction() == 0.0, timeout=5000)


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
```

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: all tests pass (engine, UI, and `tests/test_main.py`); no failures or errors. If `test_main.py` fails because `MainWindow()` can't be built, re-check that `main_window.py` matches Step 1 exactly.

- [ ] **Step 6: Manual check in the real app**

Run: `uv run wallgen`

Verify, in order:
1. The window opens with "Press Generate" in the preview area. Nothing renders until you press Generate.
2. Press **Generate**: the progress track fills briefly, then a PCB preview fades in.
3. Switch Style to Terminal, Palette to Amber, Size to uw-1440; the preview is unchanged until you press Generate, then it shows an amber terminal at the 3440x1440 aspect (letterboxed).
4. In the Terminal panel type a user and a session script, press Generate, and confirm they appear in the render. Clear the user field and confirm it falls back to `you@localhost`.
5. Switch to Code block, tick/untick Gutter and Cursor, enter a Caption, and confirm the render follows.
6. Press the **⟳ dial** five times quickly: the seed changes each time, and only the last preview lands (no flicker of older ones), crossfading in.
7. Type letters into the seed field: they are rejected.

Close the window, and confirm there is no traceback in the terminal.

- [ ] **Step 7: Commit**

```bash
git add src/wallgen/ui/main_window.py src/wallgen/ui/mock_data.py tests/ui/test_main_window.py tests/ui/test_mock_data.py
git commit -m "feat: wire the main window to the engine with live threaded previews"
```

---

## Self-Review Notes

- **Spec coverage:** `jobs.py` (Task 1), `PreviewPane` + `fit_rect` + crossfade + error line + empty hint (Task 2), `ProgressTrack` and editable `SeedField` (Task 3), editable spec-backed style panel with `values()` and empty-means-default (Task 4), engine-fed combos, `current_spec()`, Generate and ⟳ wiring, controller signal connections, docstring update, mock removal (Task 5). Manual check from the spec is Task 5 Step 6.
- **Signatures used across tasks:** `RenderController(max_width, parent)`, `submit`, `wait_for_done`, `preview_ready`/`progress`/`failed`/`busy_changed` (Task 1 → Task 5); `PreviewPane.show_image/show_error/has_image/image_size/error_text/is_fading` (Task 2 → Task 5); `ProgressTrack.set_fraction/fraction` and `SeedField.seed/set_seed` (Task 3 → Task 5); `StyleOptionsPanel.values/editor/set_style`, `STYLE_ORDER`, `STYLE_LABELS` (Task 4 → Task 5).
- **Not in this plan:** the untracked `.graphify/` ignore entry in `.gitignore` is a separate, uncommitted change.
