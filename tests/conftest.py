import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(autouse=True)
def isolated_app_data(monkeypatch, tmp_path):
    """Tests must never create or modify the user's real wallpaper library."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))


@pytest.fixture(autouse=True)
def no_real_monitors(monkeypatch):
    """Windows test runners have real monitors; tests that want some fake them."""
    from wallgen.ui import main_window

    monkeypatch.setattr(main_window, "detect_monitors", lambda screens: [])
