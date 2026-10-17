from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from wallgen.platform_win.monitors import enable_dpi_awareness
from wallgen.ui.main_window import MainWindow


def main() -> int:
    # Before QApplication, or Windows reports scaled (logical) monitor sizes.
    enable_dpi_awareness()
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
