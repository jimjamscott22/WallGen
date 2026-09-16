from PySide6.QtWidgets import QApplication

import wallgen.__main__ as wallgen_main


def test_main_shows_a_window_and_returns_exec_code(qtbot, monkeypatch):
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)
    exit_code = wallgen_main.main()
    assert exit_code == 0
