import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(autouse=True)
def isolated_app_data(monkeypatch, tmp_path):
    """Tests must never create or modify the user's real wallpaper library."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
