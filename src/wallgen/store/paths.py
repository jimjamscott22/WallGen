"""Persistent render files; the searchable library arrives in milestone 4."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from PIL import Image


def library_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / "AppData" / "Local"
    return base / "WallGen" / "library"


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
