from __future__ import annotations

from typing import Callable

from PIL import Image

from wallgen.engine.common import EngineError
from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import PALETTES, SIZES, RenderSpec
from wallgen.engine.styles.codeblock import render_codeblock
from wallgen.engine.styles.coderain import render_coderain
from wallgen.engine.styles.pcb import render_pcb
from wallgen.engine.styles.terminal import render_terminal

__all__ = ["render", "preview", "RenderSpec", "EngineError", "SIZES", "PALETTES"]

ProgressFn = Callable[[float, str], None]

_STYLES = {
    "pcb": render_pcb,
    "coderain": render_coderain,
    "terminal": render_terminal,
    "codeblock": render_codeblock,
}


def render(spec: RenderSpec, progress: ProgressFn | None = None) -> Image.Image:
    on_progress = progress or (lambda fraction, note: None)
    on_progress(0.0, "starting")
    ctx = Ctx(spec)
    image = _STYLES[spec.style](ctx, spec, on_progress)
    on_progress(1.0, "done")
    return image


def preview(spec: RenderSpec, max_width: int = 1280, progress: ProgressFn | None = None) -> Image.Image:
    scale = min(1.0, max_width / spec.width)
    return render(spec.at(round(spec.width * scale), round(spec.height * scale)), progress=progress)
