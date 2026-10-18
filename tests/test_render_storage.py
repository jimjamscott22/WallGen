from PIL import Image
import pytest

from wallgen.store.paths import library_dir, save_render


def test_library_uses_localappdata(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert library_dir() == tmp_path / "WallGen" / "library"


def test_saves_unique_full_resolution_files(tmp_path):
    image = Image.new("RGB", (640, 360), (12, 34, 56))
    first = save_render(image, tmp_path / "library")
    second = save_render(image, tmp_path / "library")
    assert first != second
    with Image.open(first) as saved:
        assert saved.size == image.size
        assert saved.tobytes() == image.tobytes()
    assert second.is_file()


def test_incomplete_save_is_cleaned(monkeypatch, tmp_path):
    def fail(self, path, **kwargs):
        path.write_bytes(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr(Image.Image, "save", fail)
    with pytest.raises(OSError, match="disk full"):
        save_render(Image.new("RGB", (1, 1)), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_data_dir_follows_localappdata(monkeypatch, tmp_path):
    from wallgen.store.paths import data_dir

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert data_dir() == tmp_path / "WallGen"
    assert library_dir().parent == data_dir()


def test_first_run_creates_the_data_folders(monkeypatch, tmp_path):
    from wallgen.store.paths import ensure_data_dirs

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    root = ensure_data_dirs()
    assert root == tmp_path / "WallGen"
    assert (root / "library").is_dir() and (root / "thumbs").is_dir()
    assert sorted(p.name for p in root.iterdir()) == ["library", "thumbs"]  # probe removed
    assert ensure_data_dirs() == root  # idempotent


def test_data_folder_errors_name_the_problem(tmp_path):
    from wallgen.store.paths import ensure_data_dirs

    blocker = tmp_path / "WallGen"
    blocker.write_text("a file where the folder should be")
    with pytest.raises(OSError):
        ensure_data_dirs(blocker)
