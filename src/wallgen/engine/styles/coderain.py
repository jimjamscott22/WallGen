from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from wallgen.engine.common import finish, font, has_cjk, mul
from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec

KATA = [chr(c) for c in range(0x30A1, 0x30FA)]
LATG = list("0123456789<>[]{}/\\|=+*#$%&@ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def render_coderain(ctx: Ctx, spec: RenderSpec, progress) -> Image.Image:
    W, H, p = ctx.W, ctx.H, ctx.pal
    head_col = p["spark"]

    def pick():
        use_kata = has_cjk() and spec.glyphs != "ascii" and ctx.rng.random() < 0.62
        return ctx.rng.choice(KATA) if use_kata else ctx.rng.choice(LATG)

    def plane(size, columns, tail, bright, head_frac, jitter=0.0):
        lay = Image.new("RGB", (W, H), (0, 0, 0))
        d = ImageDraw.Draw(lay)
        fk, fl = font("cjk", size), font("mono_b", size * 0.92)
        step = int(size * 1.16)
        for _ in range(columns):
            x = ctx.rng.uniform(-size, W + size)
            n = ctx.rng.randint(*tail)
            head_y = ctx.rng.uniform(-H * 0.5, H * 1.35)
            side = ctx.quiet(x, head_y) * 0.6 + 0.4
            for j in range(n):
                y = head_y - j * step
                if y < -size or y > H:
                    continue
                t = j / max(1, n - 1)
                fade = (1.0 - t) ** 1.55
                if ctx.rng.random() < 0.10:
                    fade *= ctx.rng.uniform(0.2, 0.6)
                if j == 0 and ctx.rng.random() < head_frac:
                    col, f = head_col, 1.0
                else:
                    col = p["primary"] if fade > 0.45 else p["primary_dim"]
                    f = fade
                f *= bright * side
                if f < 0.03:
                    continue
                ch = pick()
                fnt = fk if ord(ch) > 0x3000 else fl
                xx = x + (ctx.rng.uniform(-jitter, jitter) if jitter else 0)
                d.text((xx, y), ch, font=fnt, fill=mul(col, f))
        return lay

    progress(0.1, "rendering rain")

    # columns scale with how many glyph-widths fit across the canvas, and tails
    # with how many glyph-heights fit down it, so density holds at any aspect
    cw = max(0.35, (W / 2560.0) / ctx.U)
    tl = max(0.5, (H / 1440.0) / ctx.U)
    T = lambda lo, hi: (max(3, int(lo * tl)), max(5, int(hi * tl)))
    far  = plane(ctx.u(15), int(150 * cw), T(14, 40), 0.34, 0.22)
    mid  = plane(ctx.u(26), int(105 * cw), T(10, 30), 0.88, 0.62)
    hero = plane(ctx.u(30), int(26 * cw),  T(6, 20),  1.55, 1.00)
    near = plane(ctx.u(58), int(14 * cw),  T(4, 12),  0.70, 0.45, jitter=ctx.u(1.5))
    progress(0.6, "layering depth planes")

    arr = lambda im: np.asarray(im, np.float32)
    g = lambda im, r, gn: arr(im.filter(ImageFilter.GaussianBlur(ctx.u(r)))) * gn

    y, _ = np.mgrid[0:H, 0:W].astype(np.float32)
    out = np.zeros((H, W, 3), np.float32)
    for i in range(3):
        out[..., i] = p["bg"][i] + (p["primary"][i] / 255.0) * (4 + 6 * (1 - y / H) ** 2)

    out += arr(far.filter(ImageFilter.GaussianBlur(ctx.u(1.1)))) * 0.9
    out += g(far, 6, 0.20)
    out += arr(mid) * 1.0
    out += g(mid, 3, 0.50) + g(mid, 12, 0.32) + g(mid, 44, 0.20)
    out += arr(hero) * 1.0
    out += g(hero, 4, 0.75) + g(hero, 16, 0.48) + g(hero, 58, 0.30)
    out += arr(near.filter(ImageFilter.GaussianBlur(ctx.u(7)))) * 0.85
    out += g(near, 26, 0.30)
    out *= (1.0 - 0.055 * (np.sin(y * np.pi) * 0.5 + 0.5))[..., None]
    progress(0.9, "compositing")
    return finish(ctx, out, 0.50)
