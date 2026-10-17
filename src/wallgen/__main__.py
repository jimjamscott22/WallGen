"""Entry point: `wallgen` opens the window; `wallgen render|list` is the CLI.

Qt is imported only for the window, so the CLI runs on machines with no display.
"""

from __future__ import annotations

import sys

from wallgen import cli
from wallgen.platform_win.monitors import enable_dpi_awareness
from wallgen.store.paths import data_dir, ensure_data_dirs


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if len(argv) > 1 and argv[1] in (*cli.COMMANDS, "-h", "--help"):
        return cli.main(argv[1:])
    return _gui(argv)


def _gui(argv: list[str]) -> int:
    # Before QApplication, or Windows reports scaled (logical) monitor sizes.
    enable_dpi_awareness()

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox

    from wallgen import selftest
    from wallgen.resources import ICON_PATH

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

    from wallgen.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
