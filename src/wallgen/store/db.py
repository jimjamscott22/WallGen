"""SQLite wallpaper library. Each operation owns its connection, including workers."""

from __future__ import annotations

from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from PIL import Image

from wallgen.engine import RenderSpec
from wallgen.store.paths import library_dir, save_render


@dataclass(frozen=True)
class Wallpaper:
    id: str
    created_at: str
    spec: RenderSpec
    favorite: bool
    last_set_at: str | None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LibraryStore:
    def __init__(self, root: Path | None = None):
        self.root = (root if root is not None else library_dir().parent).resolve()
        self.image_dir = self.root / "library"
        self.thumb_dir = self.root / "thumbs"
        self.db_path = self.root / "wallgen.db"

    @contextmanager
    def _connection(self):
        self.root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise ValueError("This library was created by a newer version of WallGen.")
            if version == 0:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("""CREATE TABLE IF NOT EXISTS wallpaper (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                    style TEXT NOT NULL, palette TEXT NOT NULL,
                    width INTEGER NOT NULL, height INTEGER NOT NULL, seed INTEGER NOT NULL,
                    spec_json TEXT NOT NULL, favorite INTEGER NOT NULL DEFAULT 0,
                    last_set_at TEXT
                )""")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_created ON wallpaper(created_at DESC)")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_favorite ON wallpaper(favorite, created_at DESC)")
                connection.execute("PRAGMA user_version = 1")
                connection.commit()
            with connection:
                yield connection
        finally:
            connection.close()

    def image_path(self, item_id: str) -> Path:
        return self.image_dir / f"{self._valid_id(item_id)}.png"

    def thumbnail_path(self, item_id: str) -> Path:
        return self.thumb_dir / f"{self._valid_id(item_id)}.jpg"

    @staticmethod
    def _valid_id(item_id: str) -> str:
        if len(item_id) != 32 or any(c not in "0123456789abcdef" for c in item_id):
            raise ValueError("Invalid wallpaper ID")
        return item_id

    @staticmethod
    def _item(row) -> Wallpaper:
        return Wallpaper(row["id"], row["created_at"], RenderSpec(**json.loads(row["spec_json"])),
                         bool(row["favorite"]), row["last_set_at"])

    def save(self, image: Image.Image, spec: RenderSpec) -> Path:
        """Save full image + thumbnail before publishing its database entry."""
        if image.size != (spec.width, spec.height):
            raise ValueError("Rendered image dimensions do not match the saved settings.")
        path = save_render(image, self.image_dir)
        thumbnail = self.thumbnail_path(path.stem)
        temporary = thumbnail.with_suffix(".tmp")
        try:
            self.thumb_dir.mkdir(parents=True, exist_ok=True)
            thumb = image.convert("RGB")
            thumb.thumbnail((480, 480), Image.Resampling.LANCZOS)
            thumb.save(temporary, format="JPEG", quality=85)
            temporary.replace(thumbnail)
            with self._connection() as connection:
                connection.execute(
                    """INSERT INTO wallpaper
                    (id, created_at, style, palette, width, height, seed, spec_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (path.stem, _now(), spec.style, spec.palette, spec.width, spec.height,
                     spec.seed, json.dumps(asdict(spec), ensure_ascii=False)),
                )
        except Exception:
            for file in (path, thumbnail, temporary):
                with suppress(OSError):
                    file.unlink(missing_ok=True)
            raise
        return path

    def list(self, search: str = "", favorites_only: bool = False,
             limit: int = 100, offset: int = 0) -> list[Wallpaper]:
        # Literal substring search, including custom text and seed in the full spec.
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT * FROM wallpaper WHERE (? = 0 OR favorite = 1)
                AND instr(lower(spec_json), lower(?)) > 0
                ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?""",
                (int(favorites_only), search.strip(), limit, offset),
            ).fetchall()
        return [self._item(row) for row in rows]

    def get(self, item_id: str) -> Wallpaper:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM wallpaper WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            raise ValueError("This wallpaper is no longer in the library.")
        return self._item(row)

    def favorite(self, item_id: str, value: bool) -> None:
        with self._connection() as connection:
            connection.execute("UPDATE wallpaper SET favorite = ? WHERE id = ?", (int(value), item_id))

    def mark_set(self, item_id: str) -> None:
        with self._connection() as connection:
            connection.execute("UPDATE wallpaper SET last_set_at = ? WHERE id = ?", (_now(), item_id))

    def delete(self, item_id: str) -> bool:
        """Delete entry/files, retaining previously applied PNGs for Windows.

        Stage files beside their originals so a database error can restore them.
        Returns whether the desktop image was retained.
        """
        moved: list[tuple[Path, Path]] = []
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT last_set_at FROM wallpaper WHERE id = ?", (item_id,)).fetchone()
            if row is None:
                raise ValueError("This wallpaper is no longer in the library.")
            retained = row[0] is not None
            files = [self.thumbnail_path(item_id)]
            if not retained:
                files.append(self.image_path(item_id))
            try:
                for original in files:
                    staged = original.with_suffix(original.suffix + ".deleting")
                    if original.exists():
                        original.replace(staged)
                        moved.append((original, staged))
                connection.execute("DELETE FROM wallpaper WHERE id = ?", (item_id,))
                connection.commit()
            except Exception:
                for original, staged in reversed(moved):
                    staged.replace(original)
                raise
        for _, staged in moved:
            with suppress(OSError):
                staged.unlink(missing_ok=True)
        return retained
