# WallGen UI Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the WallGen main window as a real, running PySide6 application — matching the approved instrument-panel design exactly — wired to mock data, with no render engine behind it yet.

**Architecture:** A single `QMainWindow` (`MainWindow`) assembles five horizontal bands (header, control rail, main area, set-on row, library row) from small, focused custom widgets. A `theme.py` module holds every design token and the QSS stylesheet as pure data/functions, so visual regressions are testable without a display. Mock data stands in for the engine (styles/palettes), the store (library items), and monitor detection (set-on chips) until those subsystems exist.

**Tech Stack:** Python 3.12, PySide6 >= 6.11, `uv` for packaging, `pytest` + `pytest-qt` for tests (run with `QT_QPA_PLATFORM=offscreen`, no display server required).

**Spec:** [docs/wallgen-spec.md](../../wallgen-spec.md) (architecture, §2, §6) and the approved design canvas (copper/verdigris instrument-panel system: [https://claude.ai/artifact/Ewa3HUNNx3iNiPv9A8BELM](https://claude.ai/artifact/Ewa3HUNNx3iNiPv9A8BELM)) — this plan implements the design canvas's visual language in real Qt widgets.

## Global Constraints

- Python >= 3.12, PySide6 >= 6.11 (spec §2 stack table).
- Package management is `uv` only: `pyproject.toml` with `[project.dependencies]` / `[dependency-groups] dev = [...]`, `uv sync`, `uv add`, `uv run` — never `pip`, never `requirements.txt`. Commit `uv.lock`; gitignore `.venv/`.
- Source layout is `src/wallgen/...` (spec §2, and required by the packaging command in spec §8: `src/wallgen/__main__.py`).
- Exact design tokens (from the approved canvas, not to be approximated):
  - `BG_WINDOW = "#1B1917"`, `BG_PANEL = "#242019"`, `BG_VIEWPORT = "#08090A"`, `BG_SEED = "#16140F"`
  - `HAIRLINE = "#3A3229"`
  - `TEXT_PRIMARY = "#EDE6D8"`, `TEXT_MUTED = "#8C8272"`
  - `COPPER_LIGHT = "#E4A574"`, `COPPER = "#B26A3E"`, `COPPER_HOVER = "#C67A4B"`, `COPPER_DARK = "#6B3D22"`
  - `VERDIGRIS = "#4FA695"`
  - UI font stack: `'Archivo Narrow', 'Arial Narrow', sans-serif`. Data/mono font stack: `'JetBrains Mono', 'Consolas', monospace`. (Bundling the actual font files is a packaging follow-up, spec §8 — out of scope here; system fallbacks are used.)
- Copy rules from the design review: sentence case labels, never tracked-out ALL CAPS; no emoji anywhere (icons are inline SVG/painted glyphs); no middle-dot- or em-dash-joined meta strings.
- No render engine, no SQLite, no Windows COM calls in this plan — all content-shaped data (styles, palettes, monitors, library items) comes from `wallgen/ui/mock_data.py`.

---

## File Structure

```
pyproject.toml
uv.lock
src/wallgen/
├─ __init__.py
├─ __main__.py            entry point: `uv run wallgen`
└─ ui/
   ├─ __init__.py
   ├─ theme.py             color/font tokens + stylesheet() -> str
   ├─ mock_data.py          placeholder styles/palettes/monitors/library
   ├─ widgets.py            StatusDot, SeedField, RerollDial, MonitorChip, LibraryThumbnail
   ├─ style_options.py      StyleOptionsPanel + STYLE_LABELS/STYLE_ORDER
   └─ main_window.py        MainWindow: assembles everything
tests/
├─ conftest.py              forces the offscreen Qt platform
├─ test_main.py
└─ ui/
   ├─ test_theme.py
   ├─ test_mock_data.py
   ├─ test_widgets.py
   ├─ test_style_options.py
   └─ test_main_window.py
```

---

### Task 1: Project scaffold + minimal window

**Files:**
- Create: `pyproject.toml`
- Create: `tests/conftest.py`
- Create: `src/wallgen/__init__.py`
- Create: `src/wallgen/ui/__init__.py`
- Create: `src/wallgen/ui/main_window.py`
- Test: `tests/ui/test_main_window.py`

**Interfaces:**
- Produces: `wallgen.ui.main_window.MainWindow` — a `QMainWindow` subclass, no-arg constructor, `windowTitle()` returns `"WallGen"`, initial size 1440x900.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "wallgen"
version = "0.1.0"
description = "Procedural desktop wallpapers for Windows."
requires-python = ">=3.12"
dependencies = [
    "pyside6>=6.11",
]

[project.scripts]
wallgen = "wallgen.__main__:main"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-qt>=4.4",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/wallgen"]
```

- [ ] **Step 2: Sync the environment**

Run: `uv sync`
Expected: creates `.venv/` and `uv.lock`, installs PySide6, pytest, pytest-qt.

- [ ] **Step 3: Create `tests/conftest.py` to force headless Qt**

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

This must be the first thing pytest imports, before any `PySide6` import happens anywhere in the test session, so it lives alone at the top of `conftest.py` with no other imports above it.

- [ ] **Step 4: Create package `__init__.py` files**

`src/wallgen/__init__.py`:

```python
```

(empty — just marks the package)

`src/wallgen/ui/__init__.py`:

```python
```

- [ ] **Step 5: Write the failing test for `MainWindow`**

`tests/ui/test_main_window.py`:

```python
from wallgen.ui.main_window import MainWindow


def test_window_title_and_size(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.windowTitle() == "WallGen"
    assert window.size().width() == 1440
    assert window.size().height() == 900
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/ui/test_main_window.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wallgen.ui.main_window'`

- [ ] **Step 7: Write minimal `MainWindow`**

`src/wallgen/ui/main_window.py`:

```python
from __future__ import annotations

from PySide6.QtWidgets import QMainWindow


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("WallGen")
        self.resize(1440, 900)
```

- [ ] **Step 8: Run test to verify it passes**

Run: `uv run pytest tests/ui/test_main_window.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock tests/conftest.py src/wallgen/__init__.py src/wallgen/ui/__init__.py src/wallgen/ui/main_window.py tests/ui/test_main_window.py
git commit -m "feat: scaffold wallgen package with a minimal main window"
```

---

### Task 2: Theme tokens and stylesheet

**Files:**
- Create: `src/wallgen/ui/theme.py`
- Modify: `src/wallgen/ui/main_window.py`
- Test: `tests/ui/test_theme.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `wallgen.ui.theme` module-level string constants `BG_WINDOW, BG_PANEL, BG_VIEWPORT, BG_SEED, HAIRLINE, TEXT_PRIMARY, TEXT_MUTED, COPPER_LIGHT, COPPER, COPPER_HOVER, COPPER_DARK, VERDIGRIS, FONT_UI, FONT_MONO`; dict `COLORS`; function `stylesheet() -> str`.

- [ ] **Step 1: Write the failing test**

`tests/ui/test_theme.py`:

```python
from wallgen.ui import theme


def test_color_tokens_match_approved_design():
    assert theme.BG_WINDOW == "#1B1917"
    assert theme.BG_PANEL == "#242019"
    assert theme.BG_VIEWPORT == "#08090A"
    assert theme.BG_SEED == "#16140F"
    assert theme.HAIRLINE == "#3A3229"
    assert theme.TEXT_PRIMARY == "#EDE6D8"
    assert theme.TEXT_MUTED == "#8C8272"
    assert theme.COPPER_LIGHT == "#E4A574"
    assert theme.COPPER == "#B26A3E"
    assert theme.COPPER_HOVER == "#C67A4B"
    assert theme.COPPER_DARK == "#6B3D22"
    assert theme.VERDIGRIS == "#4FA695"


def test_stylesheet_uses_the_tokens():
    css = theme.stylesheet()
    assert theme.BG_WINDOW in css
    assert theme.COPPER in css
    assert "QPushButton#generate" in css


def test_colors_dict_matches_constants():
    assert theme.COLORS["copper"] == theme.COPPER
    assert theme.COLORS["verdigris"] == theme.VERDIGRIS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/test_theme.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wallgen.ui.theme'`

- [ ] **Step 3: Write `theme.py`**

`src/wallgen/ui/theme.py`:

```python
"""Design tokens and QSS for WallGen's instrument-panel theme.

Chrome stays muted (charcoal + copper); saturated color is reserved for
the generated wallpaper preview itself. See the approved design canvas
for the full rationale.
"""

BG_WINDOW = "#1B1917"
BG_PANEL = "#242019"
BG_VIEWPORT = "#08090A"
BG_SEED = "#16140F"

HAIRLINE = "#3A3229"

TEXT_PRIMARY = "#EDE6D8"
TEXT_MUTED = "#8C8272"

COPPER_LIGHT = "#E4A574"
COPPER = "#B26A3E"
COPPER_HOVER = "#C67A4B"
COPPER_DARK = "#6B3D22"

VERDIGRIS = "#4FA695"

FONT_UI = "'Archivo Narrow', 'Arial Narrow', sans-serif"
FONT_MONO = "'JetBrains Mono', 'Consolas', monospace"

COLORS = {
    "bg_window": BG_WINDOW,
    "bg_panel": BG_PANEL,
    "bg_viewport": BG_VIEWPORT,
    "bg_seed": BG_SEED,
    "hairline": HAIRLINE,
    "text_primary": TEXT_PRIMARY,
    "text_muted": TEXT_MUTED,
    "copper_light": COPPER_LIGHT,
    "copper": COPPER,
    "copper_hover": COPPER_HOVER,
    "copper_dark": COPPER_DARK,
    "verdigris": VERDIGRIS,
}


def stylesheet() -> str:
    return f"""
    QMainWindow, QWidget#root {{
        background: {BG_WINDOW};
        color: {TEXT_PRIMARY};
        font-family: {FONT_UI};
    }}
    QLabel {{
        color: {TEXT_PRIMARY};
        background: transparent;
        font-family: {FONT_UI};
    }}
    QLabel[role="field-label"] {{
        color: {TEXT_MUTED};
        font-size: 11px;
    }}
    QLabel[role="value"] {{
        color: {TEXT_PRIMARY};
        font-family: {FONT_MONO};
        font-size: 14px;
    }}
    QFrame[role="hairline"] {{
        background: {HAIRLINE};
        max-height: 1px;
        min-height: 1px;
        border: none;
    }}
    QFrame[role="panel"] {{
        background: {BG_PANEL};
        border: 1px solid {HAIRLINE};
        border-radius: 4px;
    }}
    QFrame[role="viewport"] {{
        background: {BG_VIEWPORT};
        border: 1px solid {HAIRLINE};
        border-radius: 4px;
    }}
    QFrame[role="chip"] {{
        background: transparent;
        border: 1px solid {HAIRLINE};
        border-radius: 3px;
    }}
    QFrame[role="chip-active"] {{
        background: transparent;
        border: 1px solid {COPPER};
        border-radius: 3px;
    }}
    QFrame[role="sprocket"] {{
        background: {HAIRLINE};
        border: none;
    }}
    QComboBox {{
        background: transparent;
        color: {TEXT_PRIMARY};
        font-family: {FONT_UI};
        font-weight: 600;
        font-size: 14px;
        border: none;
        padding: 2px 0;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 16px;
    }}
    QPushButton#generate {{
        background: {COPPER};
        color: {BG_WINDOW};
        font-family: {FONT_UI};
        font-weight: 700;
        font-size: 14px;
        border: none;
        border-radius: 3px;
        padding: 10px 22px;
    }}
    QPushButton#generate:hover {{
        background: {COPPER_HOVER};
    }}
    """
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/ui/test_theme.py -v`
Expected: PASS

- [ ] **Step 5: Apply the stylesheet in `MainWindow`**

Modify `src/wallgen/ui/main_window.py`:

```python
from __future__ import annotations

from PySide6.QtWidgets import QMainWindow

from wallgen.ui import theme


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("WallGen")
        self.resize(1440, 900)
        self.setStyleSheet(theme.stylesheet())
```

- [ ] **Step 6: Add and run the regression test**

Add to `tests/ui/test_main_window.py`:

```python
def test_window_applies_theme_stylesheet(qtbot):
    from wallgen.ui import theme

    window = MainWindow()
    qtbot.addWidget(window)
    assert theme.COPPER in window.styleSheet()
```

Run: `uv run pytest tests/ui/test_main_window.py tests/ui/test_theme.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add src/wallgen/ui/theme.py src/wallgen/ui/main_window.py tests/ui/test_theme.py tests/ui/test_main_window.py
git commit -m "feat: add instrument-panel theme tokens and apply to main window"
```

---

### Task 3: Mock data

**Files:**
- Create: `src/wallgen/ui/mock_data.py`
- Test: `tests/ui/test_mock_data.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `MOCK_STYLES: list[str]`, `MOCK_PALETTES: list[str]`, `MOCK_SIZES: list[str]`, `MOCK_QUIET_ZONES: list[str]`, `MOCK_MONITORS: list[dict]` (keys `name: str, resolution: str, active: bool`), `MOCK_LIBRARY: list[dict]` (keys `style: str, dot: str, art: str`).

- [ ] **Step 1: Write the failing test**

`tests/ui/test_mock_data.py`:

```python
from wallgen.ui import mock_data


def test_mock_styles_cover_all_four_renderers():
    assert mock_data.MOCK_STYLES == ["pcb", "coderain", "terminal", "codeblock"]


def test_mock_monitors_have_required_shape():
    assert len(mock_data.MOCK_MONITORS) == 3
    for monitor in mock_data.MOCK_MONITORS:
        assert set(monitor) == {"name", "resolution", "active"}
    assert mock_data.MOCK_MONITORS[0]["active"] is True


def test_mock_library_items_reference_known_styles():
    assert len(mock_data.MOCK_LIBRARY) == 6
    for item in mock_data.MOCK_LIBRARY:
        assert set(item) == {"style", "dot", "art"}
        assert item["style"] in mock_data.MOCK_STYLES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/test_mock_data.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wallgen.ui.mock_data'`

- [ ] **Step 3: Write `mock_data.py`**

`src/wallgen/ui/mock_data.py`:

```python
"""Placeholder content standing in for the render engine, the SQLite
library, and Windows monitor detection until those subsystems exist
(spec §3, §4, §5)."""

MOCK_STYLES = ["pcb", "coderain", "terminal", "codeblock"]

MOCK_PALETTES = ["cyber", "amber", "matrix", "violet", "ice", "crimson"]

MOCK_SIZES = ["2560 x 1440", "3440 x 1440", "1920 x 1080"]

MOCK_QUIET_ZONES = ["left", "top", "none"]

MOCK_MONITORS = [
    {"name": "All", "resolution": "", "active": True},
    {"name": "DELL U2719", "resolution": "2560 x 1440", "active": False},
    {"name": "LG 24MK", "resolution": "1920 x 1080", "active": False},
]

MOCK_LIBRARY = [
    {"style": "pcb", "dot": "#45E0E8", "art": "#0E1C24"},
    {"style": "coderain", "dot": "#55B378", "art": "#03110A"},
    {"style": "terminal", "dot": "#4FA695", "art": "#050807"},
    {"style": "codeblock", "dot": "#E14FA8", "art": "#08090A"},
    {"style": "pcb", "dot": "#E0A64F", "art": "#241608"},
    {"style": "pcb", "dot": "#E05070", "art": "#240810"},
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/ui/test_mock_data.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/wallgen/ui/mock_data.py tests/ui/test_mock_data.py
git commit -m "feat: add mock data standing in for engine, store, and monitors"
```

---

### Task 4: StatusDot, SeedField, RerollDial

**Files:**
- Create: `src/wallgen/ui/widgets.py`
- Test: `tests/ui/test_widgets.py`

**Interfaces:**
- Consumes: `wallgen.ui.theme` constants (Task 2).
- Produces:
  - `StatusDot(color: str, glow: bool = False, diameter: int = 8, parent=None)` — `.color() -> str`, `.set_color(color: str) -> None`.
  - `SeedField(seed: int = 0, parent=None)` — `.seed() -> int`, `.set_seed(seed: int) -> None`.
  - `RerollDial(parent=None)` — Qt `Signal` `rerolled`, emitted once per click.

- [ ] **Step 1: Write the failing tests**

`tests/ui/test_widgets.py`:

```python
from wallgen.ui.widgets import StatusDot, SeedField, RerollDial


def test_status_dot_color_round_trip(qtbot):
    dot = StatusDot("#4FA695")
    qtbot.addWidget(dot)
    assert dot.color() == "#4FA695"
    dot.set_color("#B26A3E")
    assert dot.color() == "#B26A3E"


def test_seed_field_round_trip(qtbot):
    field = SeedField(20260813)
    qtbot.addWidget(field)
    assert field.seed() == 20260813
    field.set_seed(42)
    assert field.seed() == 42


def test_reroll_dial_emits_rerolled_on_click(qtbot):
    dial = RerollDial()
    qtbot.addWidget(dial)
    with qtbot.waitSignal(dial.rerolled, timeout=1000):
        qtbot.mouseClick(dial, Qt.LeftButton)
```

Add the `Qt` import at the top:

```python
from PySide6.QtCore import Qt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/test_widgets.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wallgen.ui.widgets'`

- [ ] **Step 3: Write `widgets.py`**

`src/wallgen/ui/widgets.py`:

```python
from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from wallgen.ui import theme


class StatusDot(QWidget):
    """A small circular status LED (power, armed, idle, or a palette tag)."""

    def __init__(self, color: str, glow: bool = False, diameter: int = 8, parent: QWidget | None = None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(diameter, diameter)
        if glow:
            effect = QGraphicsDropShadowEffect(self)
            effect.setBlurRadius(10)
            effect.setColor(QColor(color))
            effect.setOffset(0, 0)
            self.setGraphicsEffect(effect)

    def color(self) -> str:
        return self._color

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(self._color)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(self.rect())
        painter.end()


class SeedField(QFrame):
    """A recessed, monospace readout for the render seed."""

    def __init__(self, seed: int = 0, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {theme.BG_SEED}; border: 1px solid {theme.HAIRLINE}; border-radius: 3px;"
        )
        self._label = QLabel(str(seed))
        self._label.setProperty("role", "value")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.addWidget(self._label)

    def seed(self) -> int:
        return int(self._label.text())

    def set_seed(self, seed: int) -> None:
        self._label.setText(str(seed))


class RerollDial(QAbstractButton):
    """The knurled copper dial that rerolls the seed. Emits `rerolled`."""

    rerolled = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(46, 46)
        self._angle = 0.0
        self._animation = QPropertyAnimation(self, b"angle", self)
        self._animation.setDuration(350)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(360.0)
        self._animation.setEasingCurve(QEasingCurve.OutBack)
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self) -> None:
        self._animation.stop()
        self._animation.start()
        self.rerolled.emit()

    def get_angle(self) -> float:
        return self._angle

    def set_angle(self, value: float) -> None:
        self._angle = value
        self.update()

    angle = Property(float, get_angle, set_angle)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()

        gradient = QRadialGradient(
            rect.center().x() - rect.width() * 0.15,
            rect.center().y() - rect.height() * 0.22,
            rect.width() * 0.8,
        )
        gradient.setColorAt(0.0, QColor(theme.COPPER_LIGHT))
        gradient.setColorAt(0.45, QColor(theme.COPPER))
        gradient.setColorAt(1.0, QColor(theme.COPPER_DARK))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(theme.COPPER_DARK), 1))
        painter.drawEllipse(rect.adjusted(1, 1, -1, -1))

        painter.translate(rect.center())
        painter.rotate(self._angle)
        painter.translate(-rect.center())
        painter.setPen(QPen(QColor(theme.BG_WINDOW), 2.2, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        arrow_rect = QRectF(rect.center().x() - 8, rect.center().y() - 8, 16, 16)
        painter.drawArc(arrow_rect, 20 * 16, 300 * 16)
        painter.end()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/ui/test_widgets.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/wallgen/ui/widgets.py tests/ui/test_widgets.py
git commit -m "feat: add StatusDot, SeedField, and RerollDial widgets"
```

---

### Task 5: MonitorChip and LibraryThumbnail

**Files:**
- Modify: `src/wallgen/ui/widgets.py`
- Modify: `tests/ui/test_widgets.py`

**Interfaces:**
- Consumes: `StatusDot` (Task 4), `wallgen.ui.theme` (Task 2).
- Produces:
  - `MonitorChip(name: str, resolution: str, active: bool = False, parent=None)` — `.is_active() -> bool`, `.name_text() -> str`.
  - `LibraryThumbnail(style_label: str, dot_color: str, art_color: str, parent=None)` — `.style_label() -> str`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/ui/test_widgets.py`:

```python
from wallgen.ui.widgets import LibraryThumbnail, MonitorChip


def test_monitor_chip_exposes_name_and_active_state(qtbot):
    chip = MonitorChip("DELL U2719", "2560 x 1440", active=False)
    qtbot.addWidget(chip)
    assert chip.name_text() == "DELL U2719"
    assert chip.is_active() is False

    all_chip = MonitorChip("All", "", active=True)
    qtbot.addWidget(all_chip)
    assert all_chip.is_active() is True


def test_library_thumbnail_exposes_style_label(qtbot):
    thumb = LibraryThumbnail("PCB", "#45E0E8", "#0E1C24")
    qtbot.addWidget(thumb)
    assert thumb.style_label() == "PCB"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/test_widgets.py -v`
Expected: FAIL — `ImportError: cannot import name 'MonitorChip'`

- [ ] **Step 3: Add the widgets to `widgets.py`**

Add these imports to the top of `src/wallgen/ui/widgets.py`:

```python
from PySide6.QtWidgets import QVBoxLayout
```

Append to `src/wallgen/ui/widgets.py`:

```python
class MonitorChip(QFrame):
    """A labeled port on the 'Set on' row — a detected monitor, or 'All'."""

    def __init__(self, name: str, resolution: str, active: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("role", "chip-active" if active else "chip")
        self._active = active

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 8, 16, 8)
        outer.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.addStretch(1)
        dot_color = theme.VERDIGRIS if active else theme.TEXT_MUTED
        top_row.addWidget(StatusDot(dot_color, glow=active))
        outer.addLayout(top_row)

        name_label = QLabel(name)
        name_label.setProperty("role", "value")
        outer.addWidget(name_label)

        if resolution:
            res_label = QLabel(resolution)
            res_label.setProperty("role", "field-label")
            outer.addWidget(res_label)

        self._name_label = name_label

    def is_active(self) -> bool:
        return self._active

    def name_text(self) -> str:
        return self._name_label.text()


class LibraryThumbnail(QFrame):
    """One frame of the library contact sheet."""

    def __init__(self, style_label: str, dot_color: str, art_color: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedWidth(172)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        sprocket_top = QFrame()
        sprocket_top.setProperty("role", "sprocket")
        sprocket_top.setFixedHeight(6)
        outer.addWidget(sprocket_top)

        art = QFrame()
        art.setFixedHeight(88)
        art.setStyleSheet(f"background: {art_color}; border: none;")
        outer.addWidget(art)

        sprocket_bottom = QFrame()
        sprocket_bottom.setProperty("role", "sprocket")
        sprocket_bottom.setFixedHeight(6)
        outer.addWidget(sprocket_bottom)

        caption = QHBoxLayout()
        caption.setSpacing(6)
        caption.addWidget(StatusDot(dot_color))
        label = QLabel(style_label)
        label.setProperty("role", "field-label")
        caption.addWidget(label)
        caption.addStretch(1)
        outer.addLayout(caption)

        self._style_label = style_label

    def style_label(self) -> str:
        return self._style_label
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/ui/test_widgets.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/wallgen/ui/widgets.py tests/ui/test_widgets.py
git commit -m "feat: add MonitorChip and LibraryThumbnail widgets"
```

---

### Task 6: StyleOptionsPanel

**Files:**
- Create: `src/wallgen/ui/style_options.py`
- Test: `tests/ui/test_style_options.py`

**Interfaces:**
- Consumes: nothing beyond PySide6.
- Produces: `STYLE_ORDER: list[str]` (`["pcb", "coderain", "terminal", "codeblock"]`), `STYLE_LABELS: dict[str, str]` (e.g. `{"pcb": "PCB", "coderain": "Code rain", ...}`), `StyleOptionsPanel(parent=None)` — `.set_style(style: str) -> None` (raises `ValueError` for unknown style), `.current_style_label() -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/ui/test_style_options.py`:

```python
import pytest

from wallgen.ui.style_options import STYLE_LABELS, STYLE_ORDER, StyleOptionsPanel


def test_style_order_and_labels_cover_all_four_styles():
    assert STYLE_ORDER == ["pcb", "coderain", "terminal", "codeblock"]
    assert STYLE_LABELS == {
        "pcb": "PCB",
        "coderain": "Code rain",
        "terminal": "Terminal",
        "codeblock": "Code block",
    }


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/test_style_options.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wallgen.ui.style_options'`

- [ ] **Step 3: Write `style_options.py`**

`src/wallgen/ui/style_options.py`:

```python
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QStackedWidget, QVBoxLayout, QWidget

STYLE_ORDER = ["pcb", "coderain", "terminal", "codeblock"]

STYLE_LABELS = {
    "pcb": "PCB",
    "coderain": "Code rain",
    "terminal": "Terminal",
    "codeblock": "Code block",
}

_FIELDS_BY_STYLE = {
    "pcb": [("Mark", "J A M I E"), ("Submark", "BUILD 2560 x 1440"), ("Chip label", "JMI-1440")],
    "coderain": [("Density", "Medium"), ("Glyphs", "Mixed"), ("Depth planes", "4")],
    "terminal": [("User", "jamie@legion5i"), ("Session script", "$ whoami")],
    "codeblock": [("Language", "python"), ("Gutter", "On"), ("Cursor", "On")],
}


def _field_row(label_text: str, value_text: str) -> QWidget:
    row = QWidget()
    layout = QVBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    label = QLabel(label_text)
    label.setProperty("role", "field-label")
    layout.addWidget(label)

    value = QLabel(value_text)
    value.setProperty("role", "value")
    layout.addWidget(value)

    return row


class StyleOptionsPanel(QFrame):
    """The right-hand panel that swaps its fields with the selected style."""

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
        for style in STYLE_ORDER:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.setSpacing(16)
            for label_text, value_text in _FIELDS_BY_STYLE[style]:
                page_layout.addWidget(_field_row(label_text, value_text))
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/ui/test_style_options.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/wallgen/ui/style_options.py tests/ui/test_style_options.py
git commit -m "feat: add StyleOptionsPanel that swaps fields per style"
```

---

### Task 7: Assemble the full MainWindow

**Files:**
- Modify: `src/wallgen/ui/main_window.py`
- Modify: `tests/ui/test_main_window.py`

**Interfaces:**
- Consumes: `theme` (Task 2), `mock_data` (Task 3), `StatusDot/SeedField/RerollDial/MonitorChip/LibraryThumbnail` (Tasks 4–5), `StyleOptionsPanel/STYLE_LABELS/STYLE_ORDER` (Task 6).
- Produces: `MainWindow` attributes used by tests and (later) by real wiring: `.style_combo`, `.palette_combo`, `.size_combo`, `.quiet_combo`, `.seed_field`, `.reroll_dial`, `.generate_button`, `.viewport`, `.style_panel`, `.monitor_chips: list[MonitorChip]`, `.library_thumbnails: list[LibraryThumbnail]`.

- [ ] **Step 1: Write the failing tests**

Replace `tests/ui/test_main_window.py` with:

```python
from PySide6.QtCore import Qt

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/test_main_window.py -v`
Expected: FAIL — `AttributeError: 'MainWindow' object has no attribute 'style_combo'` (and similar) on the new tests; the first two pass already.

- [ ] **Step 3: Write the full `MainWindow`**

Replace `src/wallgen/ui/main_window.py`:

```python
from __future__ import annotations

import random

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from wallgen.ui import theme
from wallgen.ui.mock_data import (
    MOCK_LIBRARY,
    MOCK_MONITORS,
    MOCK_PALETTES,
    MOCK_QUIET_ZONES,
    MOCK_SIZES,
    MOCK_STYLES,
)
from wallgen.ui.style_options import STYLE_LABELS, StyleOptionsPanel
from wallgen.ui.widgets import LibraryThumbnail, MonitorChip, RerollDial, SeedField, StatusDot


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
    line.setProperty("role", "hairline")
    if vertical:
        line.setFixedWidth(1)
        line.setFixedHeight(30)
    else:
        line.setFixedHeight(1)
    return line


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("WallGen")
        self.resize(1440, 900)
        self.setStyleSheet(theme.stylesheet())

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

        self.style_combo = QComboBox()
        self.style_combo.addItems([STYLE_LABELS[s] for s in MOCK_STYLES])
        layout.addWidget(_labeled_field("Style", self.style_combo))
        layout.addWidget(_hairline(vertical=True))

        self.palette_combo = QComboBox()
        self.palette_combo.addItems([p.capitalize() for p in MOCK_PALETTES])
        layout.addWidget(_labeled_field("Palette", self.palette_combo))
        layout.addWidget(_hairline(vertical=True))

        self.size_combo = QComboBox()
        self.size_combo.addItems(MOCK_SIZES)
        layout.addWidget(_labeled_field("Size", self.size_combo))
        layout.addWidget(_hairline(vertical=True))

        self.quiet_combo = QComboBox()
        self.quiet_combo.addItems([q.capitalize() for q in MOCK_QUIET_ZONES])
        layout.addWidget(_labeled_field("Quiet zone", self.quiet_combo))

        layout.addStretch(1)

        self.seed_field = SeedField(20260813)
        layout.addWidget(_labeled_field("Seed", self.seed_field))

        self.reroll_dial = RerollDial()
        self.reroll_dial.rerolled.connect(self._on_reroll)
        layout.addWidget(self.reroll_dial)

        self.generate_button = QPushButton("Generate")
        self.generate_button.setObjectName("generate")
        self.generate_button.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.generate_button)

        self.style_combo.currentIndexChanged.connect(self._on_style_changed)
        return rail

    def _build_main_area(self) -> QWidget:
        area = QWidget()
        layout = QHBoxLayout(area)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(20)

        preview_column = QVBoxLayout()
        preview_column.setSpacing(10)

        self.viewport = QFrame()
        self.viewport.setProperty("role", "viewport")
        self.viewport.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_column.addWidget(self.viewport, 1)

        progress_track = QFrame()
        progress_track.setFixedHeight(3)
        progress_track.setStyleSheet(f"background: {theme.HAIRLINE}; border-radius: 2px;")
        preview_column.addWidget(progress_track)

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

    def _on_style_changed(self, index: int) -> None:
        self.style_panel.set_style(MOCK_STYLES[index])

    def _on_reroll(self) -> None:
        self.seed_field.set_seed(random.randint(0, 99_999_999))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/ui/test_main_window.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -v`
Expected: all tests across all files PASS.

- [ ] **Step 6: Commit**

```bash
git add src/wallgen/ui/main_window.py tests/ui/test_main_window.py
git commit -m "feat: assemble the full WallGen main window from mock data"
```

---

### Task 8: Entry point

**Files:**
- Create: `src/wallgen/__main__.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `MainWindow` (Task 7).
- Produces: `wallgen.__main__.main() -> int`.

- [ ] **Step 1: Write the failing test**

`tests/test_main.py`:

```python
from PySide6.QtWidgets import QApplication

import wallgen.__main__ as wallgen_main


def test_main_shows_a_window_and_returns_exec_code(qtbot, monkeypatch):
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)
    exit_code = wallgen_main.main()
    assert exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wallgen.__main__'`

- [ ] **Step 3: Write `__main__.py`**

`src/wallgen/__main__.py`:

```python
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from wallgen.ui.main_window import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_main.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite one more time**

Run: `uv run pytest -v`
Expected: every test in `tests/` PASSes.

- [ ] **Step 6: Commit**

```bash
git add src/wallgen/__main__.py tests/test_main.py
git commit -m "feat: wire up the wallgen entry point"
```

---

## After this plan

`uv run wallgen` launches the real window on a machine with a display. What's deliberately still mocked, and belongs to later plans per the spec's build order (§7):

- Milestone 1 (spec §3): turn `wallpaper.py` into `wallgen/engine/`, wire real renders into `.viewport` and `.style_panel`'s field values.
- Milestone 3 (spec §4): `SystemParametersInfoW` behind the Generate/Set-on controls.
- Milestone 4 (spec §5): SQLite-backed library replacing `MOCK_LIBRARY`.
- Milestone 5 (spec §4): `IDesktopWallpaper` COM + real monitor enumeration replacing `MOCK_MONITORS`.
