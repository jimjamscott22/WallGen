from __future__ import annotations

import re

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from wallgen.engine.common import C, base_gradient, down, finish, font, glow, mul
from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec

DEFAULT_SESSION = """\
$ whoami
a person who builds things
$ cat /etc/motto
"ship it, then refactor"
$ ./build --target today
[ok] compiling fundamentals
[ok] linking side projects
[..] deploying to production
$
"""


def parse_session(text):
    """Tiny DSL -> [(kind, text)] per line.
       '$ cmd' prompt+command | '[ok]/[..]/[!!] msg' status | '' blank | else output."""
    rows = []
    for raw in text.rstrip("\n").split("\n"):
        line = raw.rstrip()
        if line.startswith("$"):
            rows.append(("cmd", line[1:].strip()))
        elif re.match(r"^\[(ok|\.\.|!!)\]", line.strip()):
            m = re.match(r"^\[(ok|\.\.|!!)\]\s*(.*)$", line.strip())
            rows.append(("status:" + m.group(1), m.group(2)))
        elif not line:
            rows.append(("blank", ""))
        else:
            rows.append(("out", line))
    return rows


def render_terminal(ctx: Ctx, spec: RenderSpec, progress) -> Image.Image:
    W, H, p, S = ctx.W, ctx.H, ctx.pal, ctx.S
    rows = parse_session(spec.session_text or DEFAULT_SESSION)
    prompt = f"{spec.user}:~$ "
    grey, white = C(128, 148, 168), C(226, 240, 250)

    def width_of(kind, txt):
        if kind == "cmd":
            return len(prompt) + len(txt)
        if kind.startswith("status"):
            return len(txt) + 9
        return len(txt)

    cols = max(24, max((width_of(k, t) for k, t in rows), default=24))
    nrows = len(rows)

    # size the window to the canvas
    frac = 0.86 if (ctx.portrait or W / H < 1.4) else 0.52
    FS = (W * frac) / (cols * 0.6018)
    LH_F, PAD_F, TITLE_F = 1.62, 1.30, 1.30
    body_h = nrows * FS * LH_F + FS * PAD_F * 2 + FS * TITLE_F
    if body_h > H * 0.84:
        FS *= (H * 0.84) / body_h
    FS = max(8, FS)
    fr, fb = font("mono", FS * S), font("mono_b", FS * S)
    CHW = fr.getlength("M")
    LH = FS * LH_F * S
    PADX, PADY = FS * PAD_F * S, FS * PAD_F * 0.9 * S
    TITLE = FS * TITLE_F * S
    body_w = cols * CHW + PADX * 2
    body_h = nrows * LH + PADY * 2 + TITLE

    term, glowl = ctx.layer(), ctx.layer()
    dt, dg = ImageDraw.Draw(term), ImageDraw.Draw(glowl)
    TX = (W * S - body_w) / 2
    TY = (H * S - body_h) / 2

    dt.rounded_rectangle([TX, TY, TX + body_w, TY + body_h], radius=FS * 0.5 * S,
                         fill=mul(p["bg"], 1.15), outline=mul(p["primary"], 0.26),
                         width=max(1, int(ctx.s(ctx.u(2)))))
    dt.line([(TX, TY + TITLE), (TX + body_w, TY + TITLE)],
            fill=mul(p["primary"], 0.16), width=max(1, int(ctx.s(ctx.u(2)))))
    for i, col in enumerate([C(255, 95, 86), C(255, 189, 46), C(39, 201, 63)]):
        cx = TX + FS * S * (0.85 + i * 0.85)
        cy = TY + TITLE / 2
        rr = FS * 0.2 * S
        dt.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=mul(col, .72))
        dg.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=mul(col, .5))
    ft = font("mono", FS * 0.53 * S)
    tt = spec.title or f"bash — {spec.user}"
    dt.text((TX + body_w / 2 - dt.textlength(tt, font=ft) / 2, TY + TITLE / 2 - FS * 0.33 * S),
            tt, font=ft, fill=mul(p["primary"], 0.34))
    progress(0.3, "drawing terminal chrome")

    def put(x, y, txt, col, bold=False, hot=True):
        f = fb if bold else fr
        dt.text((x, y), txt, font=f, fill=col)
        if hot:
            dg.text((x, y), txt, font=f, fill=col)
        return x + CHW * len(txt)

    x0, y0 = TX + PADX, TY + TITLE + PADY
    for i, (kind, txt) in enumerate(rows):
        yy = y0 + i * LH
        if kind == "blank":
            continue
        if kind == "cmd":
            x = put(x0, yy, spec.user, p["primary"], True)
            x = put(x, yy, ":", grey, False, False)
            x = put(x, yy, "~", p["accent"], True)
            x = put(x, yy, "$ ", grey, False, False)
            put(x, yy, txt if txt else "_", white, txt == "")
        elif kind.startswith("status"):
            code = kind.split(":")[1]
            col = {"ok": p["ok"], "..": p["warn"], "!!": p["accent"]}[code]
            x = put(x0 + CHW * 2, yy, f"[ {code} ]", col, True)
            put(x, yy, "  " + txt, grey, False, False)
        else:
            put(x0, yy, txt, p["warn"] if txt.startswith('"') else grey,
                False, txt.startswith('"'))
    progress(0.65, "typing session")

    out = base_gradient(ctx, (0.50, 0.48), (0.50, 0.95)) * 0.78
    H_, W_ = H, W
    yy, xx = np.mgrid[0:H_, 0:W_].astype(np.float32)
    step = max(24, int(ctx.u(64)))
    grid = np.zeros((H_, W_), np.float32)
    grid[::step, :] = 1.0
    grid[:, ::step] = 1.0
    grid = np.asarray(Image.fromarray((grid * 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(0.6)), np.float32) / 255.0
    for i in range(3):
        out[..., i] += grid * (p["primary"][i] / 255.0) * 13

    out += down(ctx, term) * 1.0
    out += glow(ctx, glowl, 3, 0.55)
    out += glow(ctx, glowl, 12, 0.42)
    out += glow(ctx, glowl, 46, 0.30)
    out *= (1.0 - 0.05 * (np.sin(yy * np.pi) * 0.5 + 0.5))[..., None]
    progress(0.9, "compositing")
    return finish(ctx, out, 0.48)
