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
