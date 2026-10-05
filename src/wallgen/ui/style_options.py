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
