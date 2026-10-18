"""Persistent render paths and atomic PNG saving."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from PIL import Image


def data_dir() -> Path:
    """%LOCALAPPDATA%\\WallGen: the library, thumbnails and database live here."""
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / "AppData" / "Local"
    return base / "WallGen"


def library_dir() -> Path:
    return data_dir() / "library"


def ensure_data_dirs(root: Path | None = None) -> Path:
    """Create the data folders on first run and prove they are writable.

    Raises OSError with the offending path, so the app can say why it
    cannot start instead of failing on its first save.
    """
    root = root if root is not None else data_dir()
    for name in ("library", "thumbs"):
        (root / name).mkdir(parents=True, exist_ok=True)
    probe = root / f".write-test-{uuid4().hex}"
    try:
        probe.write_bytes(b"")
    finally:
        probe.unlink(missing_ok=True)
    return root


def save_render(image: Image.Image, directory: Path | None = None) -> Path:
    """Publish a complete PNG at a unique path, avoiding Windows' path cache."""
    directory = directory if directory is not None else library_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid4().hex}.png"
    temporary = path.with_suffix(".tmp")
    try:
        image.save(temporary, format="PNG")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path.resolve()
