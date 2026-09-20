from __future__ import annotations

import re

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from wallgen.engine.common import C, base_gradient, down, finish, font, glow, mul
from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec

DEFAULT_CODE = """\
while (alive) {
    learn();
    build();
    ship();
    sleep(6); // optional
}
"""

KEYWORDS = {"while", "for", "if", "else", "elif", "return", "def", "function", "fn",
            "const", "let", "var", "class", "struct", "import", "from", "export",
            "async", "await", "try", "catch", "except", "with", "in", "of", "new",
            "match", "pub", "use", "impl", "do", "end", "then", "yield", "lambda"}

TOKEN_RE = re.compile(r"""
    (?P<comment>//[^\n]*|\#[^\n]*)
   |(?P<string>"[^"]*"|'[^']*')
   |(?P<number>\b\d+(?:\.\d+)?\b)
   |(?P<call>[A-Za-z_][A-Za-z_0-9]*(?=\s*\())
   |(?P<word>[A-Za-z_][A-Za-z_0-9]*)
   |(?P<space>[ \t]+)
   |(?P<punct>.)
""", re.X)


def render_codeblock(ctx: Ctx, spec: RenderSpec, progress) -> Image.Image:
    W, H, p, S = ctx.W, ctx.H, ctx.pal, ctx.S
    lines = (spec.code_text or DEFAULT_CODE).rstrip("\n").split("\n")
    cols = max(len(l) for l in lines)
    nrows = len(lines)

    frac = 0.88 if (ctx.portrait or W / H < 1.4) else 0.60
    FS = (W * frac) / (cols * 0.6018)
    LH_F = 1.44
    if nrows * FS * LH_F > H * 0.62:
        FS = (H * 0.62) / (nrows * LH_F)
    fr, fb = font("mono", FS * S), font("mono_b", FS * S)
    CHW = fr.getlength("M")
    LH = FS * LH_F * S

    text_w = cols * CHW
    text_h = LH * nrows
    layer, hotl = ctx.layer(), ctx.layer()
    d, dh = ImageDraw.Draw(layer), ImageDraw.Draw(hotl)

    X0 = (W * S - text_w) / 2 + FS * 0.6 * S
    Y0 = (H * S - text_h) / 2
    if ctx.zone == "left":
        X0 = max(X0, W * S * 0.26)
    elif ctx.zone == "right":
        X0 = min(X0, W * S * 0.74 - text_w)
    elif ctx.zone == "top":
        Y0 = max(Y0, H * S * 0.24)

    COMM  = mul(p["primary"], 0.34)
    PUNCT = C(120, 142, 162)
    VAR   = C(200, 220, 236)
    colors = dict(comment=COMM, string=p["warn"], number=p["rare"],
                  call=p["primary"], keyword=p["accent"], word=VAR,
                  space=None, punct=PUNCT)

    if spec.gutter:
        fnum = font("mono", FS * 0.34 * S)
        for i in range(nrows):
            d.text((X0 - FS * 0.9 * S, Y0 + i * LH + FS * 0.30 * S), f"{i + 1:>2}",
                   font=fnum, fill=mul(p["primary"], 0.22))
        d.line([(X0 - FS * 0.36 * S, Y0 - FS * 0.16 * S),
                (X0 - FS * 0.36 * S, Y0 + text_h - LH * 0.28)],
               fill=mul(p["primary"], 0.16), width=max(1, int(ctx.s(ctx.u(2)))))
    progress(0.3, "drawing gutter")

    for i, line in enumerate(lines):
        cx = X0
        for m in TOKEN_RE.finditer(line):
            kind = m.lastgroup
            txt = m.group()
            if kind == "space":
                cx += CHW * len(txt)
                continue
            if kind == "word" and txt in KEYWORDS:
                kind = "keyword"
            col = colors.get(kind, VAR)
            bold = kind in ("keyword", "call")
            f = fb if bold else fr
            d.text((cx, Y0 + i * LH), txt, font=f, fill=col)
            if kind in ("keyword", "call", "number", "string"):
                dh.text((cx, Y0 + i * LH), txt, font=f, fill=col)
            cx += CHW * len(txt)
    progress(0.65, "highlighting syntax")

    if spec.caption:
        fcap = font("mono", FS * 0.33 * S)
        d.text((X0, Y0 + text_h + FS * 0.38 * S), spec.caption, font=fcap,
               fill=mul(p["primary"], 0.28))
    if spec.cursor:
        cur_x = X0 + CHW * (len(lines[-1]) + 0.4)
        cur_y = Y0 + (nrows - 1) * LH
        dh.rectangle([cur_x, cur_y + FS * 0.14 * S, cur_x + CHW * 0.62, cur_y + FS * S],
                     fill=p["primary"])

    out = base_gradient(ctx, (0.55, 0.46), (0.50, 0.95))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    step = max(20, int(ctx.u(48)))
    dot = np.zeros((H, W), np.float32)
    dot[::step, ::step] = 1.0
    dot = np.asarray(Image.fromarray((dot * 255).astype(np.uint8))
                     .filter(ImageFilter.GaussianBlur(0.9)), np.float32) / 255.0
    for i in range(3):
        out[..., i] += dot * (60 + p["primary"][i] * 0.05)

    out += down(ctx, layer) * 1.0
    out += glow(ctx, hotl, 4, 0.42)
    out += glow(ctx, hotl, 18, 0.30)
    out += glow(ctx, hotl, 60, 0.22)
    progress(0.9, "compositing")
    return finish(ctx, out, 0.50)
