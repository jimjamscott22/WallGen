from PySide6.QtWidgets import QApplication, QMessageBox

import wallgen.__main__ as wallgen_main
from wallgen import selftest
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
    exit_code = wallgen_main.main(["wallgen"])
    assert exit_code == 0
    assert shown
    for window in shown:
        window.close()


def test_main_sets_the_app_icon_and_creates_data_folders(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)
    wallgen_main.main(["wallgen"])
    app = QApplication.instance()
    assert not app.windowIcon().isNull()
    assert app.applicationName() == "WallGen"
    assert (tmp_path / "appdata" / "WallGen" / "library").is_dir()
    for widget in app.topLevelWidgets():
        widget.close()


def test_unwritable_data_folder_is_explained_not_a_crash(qtbot, monkeypatch):
    def fail(root=None):
        raise PermissionError(13, "Access is denied", "C:/Users/me/AppData/Local/WallGen")

    shown = []
    monkeypatch.setattr(wallgen_main, "ensure_data_dirs", fail)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: shown.append(args[2]))
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)
    assert wallgen_main.main(["wallgen"]) == 1
    assert "Access is denied" in shown[0]


def test_self_test_flag_runs_the_self_test_instead_of_the_window(qtbot, monkeypatch):
    monkeypatch.setattr(selftest, "run", lambda: 7)
    monkeypatch.setattr(QApplication, "exec", lambda self: 1 / 0)  # must not start the event loop
    assert wallgen_main.main(["WallGen.exe", "--self-test"]) == 7
