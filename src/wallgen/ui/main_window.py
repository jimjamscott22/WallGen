from __future__ import annotations

from PySide6.QtWidgets import QMainWindow

from wallgen.ui import theme


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("WallGen")
        self.resize(1440, 900)
        self.setStyleSheet(theme.stylesheet())
