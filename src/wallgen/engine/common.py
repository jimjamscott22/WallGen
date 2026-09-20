from __future__ import annotations

import functools
import os

import numpy as np
from PIL import Image, ImageFilter, ImageFont


class EngineError(Exception):
    """Raised when the engine can't find a resource it needs to render."""


def C(*v):
    return tuple(v)


def mul(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


# Several candidates per role so the module survives a different font set.
FONT_CANDIDATES = {
    "mono": ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
             "/System/Library/Fonts/Menlo.ttc", "C:/Windows/Fonts/consola.ttf"],
    "mono_b": ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
               "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
               "C:/Windows/Fonts/consolab.ttf"],
    "sans_b": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
               "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
               "C:/Windows/Fonts/arialbd.ttf"],
    "cjk": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
            "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
            "C:/Windows/Fonts/YuGothR.ttc",
            "C:/Windows/Fonts/meiryo.ttc",
            "C:/Windows/Fonts/msgothic.ttc"],
}


@functools.lru_cache(maxsize=1)
def _resolve_fonts() -> dict[str, str | None]:
    fonts = {role: next((c for c in cands if os.path.exists(c)), None)
              for role, cands in FONT_CANDIDATES.items()}
    if not fonts["mono"]:
        raise EngineError("no monospace font found — install fonts-dejavu-core")
    fonts["mono_b"] = fonts["mono_b"] or fonts["mono"]
    fonts["sans_b"] = fonts["sans_b"] or fonts["mono_b"]
    return fonts


def has_cjk() -> bool:
    return _resolve_fonts()["cjk"] is not None


def font(key, size):
    fonts = _resolve_fonts()
    return ImageFont.truetype(fonts[key] or fonts["mono"], max(4, int(size)))


def finish(ctx, out, extra_vignette=0.46):
    """Vignette, quiet zone, grain, filmic rolloff — shared by every style."""
    H, W = ctx.H, ctx.W
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    vx, vy = (x - W / 2) / (W / 2), (y - H / 2) / (H / 2)
    out = out * (1.0 - extra_vignette * np.clip(np.sqrt(vx * vx * 0.85 + vy * vy), 0, 1.4) ** 2.1)[..., None]
    out = out * ctx.quiet_mask()[..., None]
    out = out + np.random.default_rng(ctx.seed).normal(0, 2.0, (H, W, 1)).astype(np.float32)
    out = 255.0 * (1.0 - np.exp(-np.clip(out, 0, None) / 155.0))
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


def down(ctx, im):
    return np.asarray(im.resize((ctx.W, ctx.H), Image.LANCZOS), np.float32)


def glow(ctx, im, radius_units, gain):
    return down(ctx, im.filter(ImageFilter.GaussianBlur(ctx.u(radius_units) * ctx.S))) * gain


def base_gradient(ctx, focus=(0.66, 0.48), focus2=(0.12, 0.92)):
    H, W, p = ctx.H, ctx.W, ctx.pal
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    nx, ny = (x - W * focus[0]) / (W * 0.70), (y - H * focus[1]) / (H * 0.70)
    core = np.clip(1.0 - np.sqrt(nx * nx + ny * ny), 0, 1) ** 2.2
    nx2, ny2 = (x - W * focus2[0]) / (W * 0.52), (y - H * focus2[1]) / (H * 0.52)
    core2 = np.clip(1.0 - np.sqrt(nx2 * nx2 + ny2 * ny2), 0, 1) ** 2.6
    bg = np.zeros((H, W, 3), np.float32)
    for i in range(3):
        bg[..., i] = (p["bg"][i]
                      + core * (p["primary"][i] / 255.0) * 30
                      + core2 * (p["accent"][i] / 255.0) * 26)
    return bg
