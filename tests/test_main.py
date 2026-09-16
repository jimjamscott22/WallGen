from PySide6.QtWidgets import QApplication

import wallgen.__main__ as wallgen_main
from wallgen.ui.main_window import MainWindow


def test_main_shows_a_window_and_returns_exec_code(qtbot, monkeypatch):
    shown = []

    def fake_exec(self):
        shown.extend(
            w for w in self.topLevelWidgets()
            if isinstance(w, MainWindow) and w.isVisible()
        )
        return 0

    monkeypatch.setattr(QApplication, "exec", fake_exec)
    exit_code = wallgen_main.main()
    assert exit_code == 0
    assert shown
