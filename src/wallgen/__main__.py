from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from wallgen import selftest
from wallgen.platform_win.monitors import enable_dpi_awareness
from wallgen.resources import ICON_PATH
from wallgen.store.paths import data_dir, ensure_data_dirs
from wallgen.ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    # Before QApplication, or Windows reports scaled (logical) monitor sizes.
    enable_dpi_awareness()
    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName("WallGen")
    app.setWindowIcon(QIcon(str(ICON_PATH)))
    if selftest.FLAG in argv[1:]:
        return selftest.run()
    try:
        ensure_data_dirs()
    except OSError as exc:
        QMessageBox.critical(
            None, "WallGen",
            f"WallGen could not create its data folder:\n{data_dir()}\n\n{exc}",
        )
        return 1
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
