import sqlite3

from PIL import Image
import pytest

from wallgen.engine import RenderSpec
from wallgen.store.db import LibraryStore


@pytest.fixture
def store(tmp_path):
    return LibraryStore(tmp_path)


def save(store, seed=42, **kwargs):
    spec = RenderSpec(width=640, height=360, seed=seed, **kwargs)
    path = store.save(Image.new("RGB", (640, 360), (10, 20, 30)), spec)
    return path, spec


def test_restart_preserves_all_spec_fields_and_thumbnail(store):
    spec = RenderSpec(
        width=640, height=360, style="codeblock", seed=7, palette="amber",
        quiet_zone="top", mark="JAMIE", submark="工作", chip_label="chip",
        user="me@host", title="window", session_text="$ whoami\nme",
        code_text="print('hello')", caption="hello", glyphs="ascii", gutter=False, cursor=False,
    )
    path = store.save(Image.new("RGB", (640, 360)), spec)
    reopened = LibraryStore(store.root)
    item = reopened.list()[0]
    assert item.spec == spec
    assert reopened.image_path(item.id) == path
    with Image.open(reopened.thumbnail_path(item.id)) as thumb:
        assert thumb.format == "JPEG"
        assert thumb.size == (480, 270)
    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1


def test_favorites_search_and_pagination_survive_restart(store):
    first, _ = save(store, seed=1, caption="a literal % and _")
    second, _ = save(store, seed=2, palette="amber")
    store.favorite(first.stem, True)
    reopened = LibraryStore(store.root)
    assert [x.id for x in reopened.list(favorites_only=True)] == [first.stem]
    assert [x.id for x in reopened.list("AMBER")] == [second.stem]
    assert [x.id for x in reopened.list("%")] == [first.stem]
    assert len(reopened.list(limit=1)) == 1
    assert reopened.list(limit=1)[0].id != reopened.list(limit=1, offset=1)[0].id
    reopened.favorite(first.stem, False)
    assert not reopened.list(favorites_only=True)


def test_delete_removes_only_selected_render(store):
    first, _ = save(store, seed=1)
    second, _ = save(store, seed=2)
    legacy = store.image_dir / "legacy.png"
    legacy.write_bytes(b"unindexed milestone 3 image")
    assert store.delete(first.stem) is False
    assert not first.exists()
    assert not store.thumbnail_path(first.stem).exists()
    assert second.exists() and legacy.exists()
    assert [x.id for x in store.list()] == [second.stem]


def test_applied_wallpaper_file_survives_library_deletion(store):
    path, _ = save(store)
    store.mark_set(path.stem)
    assert LibraryStore(store.root).get(path.stem).last_set_at
    assert store.delete(path.stem) is True
    assert path.is_file()
    assert not store.list()
    assert not store.thumbnail_path(path.stem).exists()


def test_failed_thumbnail_does_not_leave_partial_record_or_png(store, monkeypatch):
    original_save = Image.Image.save

    def fail(self, fp, format=None, **kwargs):
        if format == "JPEG":
            fp.write_bytes(b"partial")
            raise OSError("disk full")
        return original_save(self, fp, format=format, **kwargs)

    monkeypatch.setattr(Image.Image, "save", fail)
    with pytest.raises(OSError, match="disk full"):
        save(store)
    assert not store.list()
    assert not list(store.image_dir.iterdir())
    assert not list(store.thumb_dir.iterdir())


def test_database_failure_cleans_new_files_and_keeps_existing(store):
    existing, _ = save(store)
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("""CREATE TRIGGER fail_insert BEFORE INSERT ON wallpaper
                            BEGIN SELECT RAISE(ABORT, 'test failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="test failure"):
        save(store, seed=2)
    assert list(store.image_dir.iterdir()) == [existing]
    assert len(list(store.thumb_dir.iterdir())) == 1


def test_delete_database_failure_restores_staged_files(store):
    path, _ = save(store)
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("""CREATE TRIGGER fail_delete BEFORE DELETE ON wallpaper
                            BEGIN SELECT RAISE(ABORT, 'test failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        store.delete(path.stem)
    assert store.get(path.stem)
    assert path.is_file() and store.thumbnail_path(path.stem).is_file()


def test_future_database_version_is_not_downgraded(store):
    store.root.mkdir(exist_ok=True)
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("PRAGMA user_version = 99")
    with pytest.raises(ValueError, match="newer version"):
        store.list()
    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 99
