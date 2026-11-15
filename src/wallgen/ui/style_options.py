from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args

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
from wallgen.engine.spec import (
    BlueprintLayout,
    BlueprintSubject,
    ContourLayout,
    ContourLines,
    RainDensity,
    TraceDensity,
)

STYLE_ORDER = ["pcb", "coderain", "terminal", "codeblock", "blueprint", "contour"]

STYLE_LABELS = {
    "pcb": "PCB",
    "coderain": "Code rain",
    "terminal": "Terminal",
    "codeblock": "Code block",
    "blueprint": "Blueprint",
    "contour": "Contour",
}

_DEFAULTS = RenderSpec()
_TEXT_BOX_HEIGHT = 120
_ROW_GAP = 16
_CHECK_GAP = 8


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
        Field("pcb_traces", "Traces", "choice", choices=get_args(TraceDensity),
              default=_DEFAULTS.pcb_traces),
        Field("pcb_hero_chip", "Hero chip", "check", default=_DEFAULTS.pcb_hero_chip),
        Field("pcb_small_chips", "Small chips", "check", default=_DEFAULTS.pcb_small_chips),
        Field("pcb_components", "Components", "check", default=_DEFAULTS.pcb_components),
    ],
    "coderain": [
        Field("glyphs", "Glyphs", "choice", choices=("mixed", "ascii"), default=_DEFAULTS.glyphs),
        Field("rain_density", "Density", "choice", choices=get_args(RainDensity),
              default=_DEFAULTS.rain_density),
        Field("rain_foreground", "Foreground streaks", "check",
              default=_DEFAULTS.rain_foreground),
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
    "blueprint": [
        Field("blueprint_subject", "Subject", "choice", choices=get_args(BlueprintSubject),
              default=_DEFAULTS.blueprint_subject),
        Field("blueprint_layout", "Layout", "choice", choices=get_args(BlueprintLayout),
              default=_DEFAULTS.blueprint_layout),
        Field("blueprint_grid", "Grid", "check", default=_DEFAULTS.blueprint_grid),
        Field("blueprint_dimensions", "Dimensions", "check",
              default=_DEFAULTS.blueprint_dimensions),
        Field("blueprint_labels", "Labels", "check", default=_DEFAULTS.blueprint_labels),
    ],
    "contour": [
        Field("contour_layout", "Layout", "choice", choices=get_args(ContourLayout),
              default=_DEFAULTS.contour_layout),
        Field("contour_lines", "Lines", "choice", choices=get_args(ContourLines),
              default=_DEFAULTS.contour_lines),
        Field("contour_accent", "Accent line", "check", default=_DEFAULTS.contour_accent),
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
            page_layout.setSpacing(0)
            previous = None
            for field in FIELDS_BY_STYLE[style]:
                editor = _make_editor(field)
                self._editors[field.key] = (field, editor)
                if previous is not None:
                    # A run of checkboxes reads as one group, and the tighter
                    # gap keeps the tallest page inside the default window.
                    grouped = field.kind == previous.kind == "check"
                    page_layout.addSpacing(_CHECK_GAP if grouped else _ROW_GAP)
                page_layout.addWidget(_field_row(field, editor))
                previous = field
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

    def load_spec(self, spec: RenderSpec) -> None:
        """Restore every style's fields, including currently hidden pages."""
        for key, (field, editor) in self._editors.items():
            value = getattr(spec, key)
            if field.kind == "line":
                editor.setText(value)
            elif field.kind == "text":
                editor.setPlainText(value)
            elif field.kind == "choice":
                editor.setCurrentText(value)
            else:
                editor.setChecked(value)
        self.set_style(spec.style)
