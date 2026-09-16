#!/usr/bin/env python3
"""
wallpaper.py — generate dark neon wallpapers at any resolution.

Four styles, all resolution-independent and deterministic:

  pcb        procedurally routed circuit board (traces never cross)
  coderain   depth-layered falling-glyph rain
  terminal   a glowing fake shell session in a window
  codeblock  a syntax-highlighted block of code as typography

Examples
  python3 wallpaper.py --style pcb --size 3440x1440 --palette amber
  python3 wallpaper.py --style terminal --size 2560x1440 --script session.txt
  python3 wallpaper.py --style codeblock --size 1179x2556 --code loop.txt --quiet-zone top
  python3 wallpaper.py --list
"""
import argparse, math, os, random, re, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np

# ----------------------------------------------------------------- presets
SIZES = {
    # 16:9
    "1080p": (1920, 1080), "1440p": (2560, 1440), "4k": (3840, 2160),
    # 16:10
    "wxga+": (1920, 1200), "wqxga": (2560, 1600), "4k-16x10": (3840, 2400),
    # ultrawide / super-ultrawide
    "uw-1080": (2560, 1080), "uw-1440": (3440, 1440), "uw-4k": (5120, 2160),
    "suw-1440": (5120, 1440),
    # 3:2, 4:3
    "surface": (2256, 1504), "ipad": (2048, 1536),
    # portrait / mobile
    "phone": (1179, 2556), "phone-qhd": (1440, 3200), "ipad-portrait": (1536, 2048),
    "portrait-1440": (1440, 2560),
}

def C(*v):
    return tuple(v)

PALETTES = {
    "cyber":  dict(primary=C(34, 226, 255),  primary_dim=C(16, 132, 165),
                   accent=C(255, 47, 200),   accent_dim=C(158, 24, 118),
                   spark=C(150, 90, 255),    rare=C(255, 170, 60),
                   ok=C(80, 240, 150),       warn=C(255, 190, 90),
                   bg=C(4, 6, 10)),
    "amber":  dict(primary=C(255, 168, 64),  primary_dim=C(150, 92, 26),
                   accent=C(255, 92, 40),    accent_dim=C(140, 44, 18),
                   spark=C(255, 214, 130),   rare=C(120, 220, 255),
                   ok=C(180, 240, 120),      warn=C(255, 120, 60),
                   bg=C(14, 8, 4)),
    "matrix": dict(primary=C(60, 255, 130),  primary_dim=C(26, 150, 78),
                   accent=C(150, 255, 190),  accent_dim=C(40, 120, 70),
                   spark=C(220, 255, 230),   rare=C(120, 255, 200),
                   ok=C(80, 240, 150),       warn=C(230, 255, 120),
                   bg=C(3, 8, 5)),
    "violet": dict(primary=C(168, 120, 255), primary_dim=C(88, 58, 158),
                   accent=C(255, 110, 220),  accent_dim=C(140, 40, 116),
                   spark=C(120, 220, 255),   rare=C(255, 200, 120),
                   ok=C(130, 240, 200),      warn=C(255, 190, 120),
                   bg=C(8, 5, 16)),
    "ice":    dict(primary=C(150, 220, 255), primary_dim=C(64, 116, 158),
                   accent=C(90, 255, 235),   accent_dim=C(30, 130, 120),
                   spark=C(230, 245, 255),   rare=C(160, 180, 255),
                   ok=C(120, 240, 200),      warn=C(255, 210, 140),
                   bg=C(4, 8, 14)),
    "crimson":dict(primary=C(255, 90, 90),   primary_dim=C(150, 40, 44),
                   accent=C(255, 170, 60),   accent_dim=C(140, 82, 20),
                   spark=C(255, 220, 200),   rare=C(120, 200, 255),
                   ok=C(255, 150, 90),       warn=C(255, 220, 120),
                   bg=C(14, 4, 6)),
}

# Several candidates per role so the script survives a different font set.
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
            "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"],
}
FONTS = {}
for _role, _cands in FONT_CANDIDATES.items():
    FONTS[_role] = next((c for c in _cands if os.path.exists(c)), None)
if not FONTS["mono"]:
    sys.exit("no monospace font found — install fonts-dejavu-core")
FONTS["mono_b"] = FONTS["mono_b"] or FONTS["mono"]
FONTS["sans_b"] = FONTS["sans_b"] or FONTS["mono_b"]
HAS_CJK = FONTS["cjk"] is not None

def font(key, size):
    return ImageFont.truetype(FONTS[key] or FONTS["mono"], max(4, int(size)))

def mul(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)

# ----------------------------------------------------------------- context
class Ctx:
    """Everything a style needs: canvas size, scale, palette, safe zone."""
    def __init__(self, a):
        self.W, self.H = a.W, a.H
        self.pal = PALETTES[a.palette]
        self.seed = a.seed
        self.zone = a.quiet_zone
        # one "unit" == 1px at 1440p; every hand-tuned constant is in units
        self.U = min(self.W, self.H) / 1440.0
        # supersample as much as the pixel budget allows
        self.S = max(1.0, min(2.0, math.sqrt(24e6 / (self.W * self.H))))
        self.area = (self.W * self.H) / (2560 * 1440)
        self.portrait = self.H > self.W
        random.seed(self.seed)

    def u(self, v):
        return v * self.U

    def s(self, v):
        return v * self.S

    def layer(self):
        return Image.new("RGB", (int(self.W * self.S), int(self.H * self.S)), (0, 0, 0))

    def quiet(self, x, y):
        """1.0 where the design may be busy, lower where icons live."""
        z, W, H = self.zone, self.W, self.H
        if z == "none":
            return 1.0
        if z == "left":
            t = x / W
        elif z == "right":
            t = 1.0 - x / W
        elif z == "top":
            t = y / H
        else:  # bottom
            t = 1.0 - y / H
        span = 0.30 if not self.portrait else 0.24
        return 0.10 + 0.90 * min(1.0, max(0.0, (t - span * 0.5) / (span * 2.2))) ** 1.7

    def quiet_mask(self):
        y, x = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
        z = self.zone
        if z == "none":
            return np.ones((self.H, self.W), np.float32)
        if z == "left":
            t = x / self.W
        elif z == "right":
            t = 1.0 - x / self.W
        elif z == "top":
            t = y / self.H
        else:
            t = 1.0 - y / self.H
        span = 0.28 if not self.portrait else 0.22
        return 1.0 - 0.32 * np.clip((span - t) / span, 0, 1) ** 1.3

# ----------------------------------------------------------------- finishing
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

# ================================================================= style: pcb
DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]

def render_pcb(ctx, a):
    W, H, p, S = ctx.W, ctx.H, ctx.pal, ctx.S
    U = ctx.U
    GS = max(3, int(ctx.u(4)))
    GW, GH = max(8, W // GS), max(8, H // GS)
    occ = Image.new("L", (GW, GH), 0)
    occ_d = ImageDraw.Draw(occ)

    def reserve(box, pad=0):
        occ_d.rectangle([(box[0] - pad) / GS, (box[1] - pad) / GS,
                         (box[2] + pad) / GS, (box[3] + pad) / GS], fill=255)

    def gen_path(x, y, steps, seglen, diag_bias=0.30):
        d = random.randrange(8)
        if random.random() > diag_bias:
            d = (d // 2) * 2
        pts = [(x, y)]
        for _ in range(steps):
            if random.random() < 0.88:
                d = (d + random.choice([-1, 1])) % 8
                if random.random() > diag_bias and d % 2 == 1:
                    d = (d + random.choice([-1, 1])) % 8
            dx, dy = DIRS[d]
            L = random.randint(*seglen)
            x, y = x + dx * L, y + dy * L
            pts.append((x, y))
            if not (-ctx.u(140) < x < W + ctx.u(140) and -ctx.u(140) < y < H + ctx.u(140)):
                break
        return pts

    def try_route(pts, clearance):
        probe = Image.new("L", (GW, GH), 0)
        ImageDraw.Draw(probe).line([(px / GS, py / GS) for px, py in pts],
                                   fill=255, width=max(1, int(clearance / GS)), joint="curve")
        pm = np.asarray(probe, bool)
        if not pm.any() or (np.asarray(occ, bool) & pm).any():
            return None
        occ.paste(Image.fromarray((np.asarray(occ, np.uint8) | (pm * 255)).astype(np.uint8)))
        return pts

    hot, soft = ctx.layer(), ctx.layer()
    d_hot, d_soft = ImageDraw.Draw(hot), ImageDraw.Draw(soft)
    sc = lambda pts: [(px * S, py * S) for px, py in pts]

    def chip(cx, cy, w, h, pins, col, glowcol, label=None, four_side=True):
        x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
        rad = min(w, h) * 0.07
        plen = min(w, h) * 0.09
        reserve((x0 - plen, y0 - plen, x1 + plen, y1 + plen), pad=ctx.u(14))
        box = [x0 * S, y0 * S, x1 * S, y1 * S]
        d_soft.rounded_rectangle(box, radius=rad * S, fill=mul(p["bg"], 1.2),
                                 outline=mul(col, .50), width=int(ctx.s(ctx.u(2.6))))
        d_hot.rounded_rectangle(box, radius=rad * S, outline=mul(col, .70),
                                width=max(1, int(ctx.s(ctx.u(1.2)))))
        m = min(w, h) * 0.16
        d_soft.rounded_rectangle([(x0 + m) * S, (y0 + m) * S, (x1 - m) * S, (y1 - m) * S],
                                 radius=rad * S, outline=mul(glowcol, .28),
                                 width=max(1, int(ctx.s(ctx.u(1.5)))))
        pw = max(1, int(ctx.s(ctx.u(2.4))))
        for i in range(pins):
            t = (i + 1) / (pins + 1)
            px_, py_ = x0 + w * t, y0 + h * t
            pc = mul(col, 0.62)
            d_soft.line([(px_ * S, y0 * S), (px_ * S, (y0 - plen) * S)], fill=pc, width=pw)
            d_soft.line([(px_ * S, y1 * S), (px_ * S, (y1 + plen) * S)], fill=pc, width=pw)
            if four_side:
                d_soft.line([(x0 * S, py_ * S), ((x0 - plen) * S, py_ * S)], fill=pc, width=pw)
                d_soft.line([(x1 * S, py_ * S), ((x1 + plen) * S, py_ * S)], fill=pc, width=pw)
        dr = min(w, h) * 0.032
        ox, oy = x0 + m * 1.5, y0 + m * 1.5
        d_hot.ellipse([(ox - dr) * S, (oy - dr) * S, (ox + dr) * S, (oy + dr) * S], fill=glowcol)
        if label:
            f = font("mono_b", min(w, h) * 0.105 * S)
            bb = d_hot.textbbox((0, 0), label, font=f)
            d_hot.text((cx * S - (bb[2] - bb[0]) / 2 - bb[0], cy * S - (bb[3] - bb[1]) / 2 - bb[1]),
                       label, font=f, fill=mul(glowcol, .62))

    # hero chip goes in the busy half, opposite the quiet zone
    hx = 0.665 if ctx.zone in ("left", "none", "top", "bottom") else 0.335
    hy = 0.455 if ctx.zone != "top" else 0.60
    HCX, HCY = W * hx, H * hy
    hero = ctx.u(400) * (1.0 if not ctx.portrait else 0.85)
    chip(HCX, HCY, hero, hero, 13, p["primary"], p["primary"], label=a.chip_label)
    for fx, fy, fw, fh, pins, col, gl, four in [
        (0.885, 0.735, 210, 132, 7, p["accent"], p["spark"], False),
        (0.360, 0.780, 176, 112, 6, p["accent"], p["accent"], False),
        (0.845, 0.180, 150, 150, 6, p["primary"], p["primary"], True),
        (0.480, 0.150, 132, 90,  5, p["primary"], p["primary"], False)]:
        chip(W * fx, H * fy, ctx.u(fw), ctx.u(fh), pins, col, gl, four_side=four)

    # wordmark keep-out
    mk_box = None
    if a.mark:
        fm = font("sans_b", ctx.u(58) * S)
        tmp = ImageDraw.Draw(Image.new("L", (8, 8)))
        tw = tmp.textlength(a.mark, font=fm) / S
        mkx, mky = W * 0.048, H * (0.795 if not ctx.portrait else 0.86)
        if ctx.zone == "right":
            mkx = W - tw - W * 0.048 - ctx.u(30)
        mk_box = (mkx, mky, mkx + tw + ctx.u(20), mky + ctx.u(150))
        reserve(mk_box, pad=ctx.u(26))

    def scatter(n, tries, steps, seglen, clearance, width, colf, hot_frac, dens=1.0):
        placed = 0
        for _ in range(tries):
            if placed >= n:
                break
            x = random.uniform(-ctx.u(100), W + ctx.u(100))
            y = random.uniform(-ctx.u(100), H + ctx.u(100))
            if random.random() > ctx.quiet(x, y) * dens:
                continue
            pts = try_route(gen_path(x, y, random.randint(*steps), seglen), clearance)
            if pts is None:
                continue
            placed += 1
            col, f = colf()
            d_soft.line(sc(pts), fill=mul(col, f), width=max(1, int(ctx.s(width))), joint="curve")
            if random.random() < hot_frac:
                d_hot.line(sc(pts), fill=mul(col, min(1.0, f * 1.5)),
                           width=max(1, int(ctx.s(width * 0.42))), joint="curve")
            for (vx, vy) in (pts[0], pts[-1]):
                if 0 < vx < W and 0 < vy < H and random.random() < 0.5:
                    r = ctx.u(random.uniform(4, 8))
                    d_soft.ellipse([(vx - r) * S, (vy - r) * S, (vx + r) * S, (vy + r) * S],
                                   outline=mul(col, f * 0.9), width=max(1, int(ctx.s(ctx.u(1.8)))))
        return placed

    A = ctx.area
    seg = lambda lo, hi: (int(ctx.u(lo)), int(ctx.u(hi)))
    scatter(int(34 * A), int(900 * A), (4, 9), seg(100, 250), ctx.u(13), ctx.u(3.6),
            lambda: ((p["primary"] if random.random() < .62 else p["accent"]),
                     random.uniform(.70, .95)), 0.95)
    scatter(int(120 * A), int(3000 * A), (3, 8), seg(70, 240), ctx.u(10), ctx.u(2.7),
            lambda: ((p["primary"] if random.random() < .70 else p["accent"]),
                     random.uniform(.34, .58)), 0.35)
    scatter(int(340 * A), int(7000 * A), (2, 6), seg(40, 160), ctx.u(7), ctx.u(1.9),
            lambda: ((p["primary_dim"] if random.random() < .74 else p["accent_dim"]),
                     random.uniform(.55, .95)), 0.10)

    for i in range(int(26 * max(1.0, A ** 0.5))):
        ang = random.uniform(0, math.tau)
        r0 = hero * 0.61
        pts = try_route(gen_path(HCX + math.cos(ang) * r0, HCY + math.sin(ang) * r0,
                                 random.randint(3, 7), seg(90, 260)), ctx.u(12))
        if pts is None:
            continue
        col = p["primary"] if i % 3 else p["accent"]
        d_soft.line(sc(pts), fill=mul(col, .72), width=max(1, int(ctx.s(ctx.u(3.2)))), joint="curve")
        d_hot.line(sc(pts), fill=col, width=max(1, int(ctx.s(ctx.u(1.4)))), joint="curve")

    def free_spot(w_, h_, pad):
        for _ in range(60):
            x, y = random.uniform(0, W), random.uniform(0, H)
            if random.random() > ctx.quiet(x, y):
                continue
            box = (x - w_ / 2 - pad, y - h_ / 2 - pad, x + w_ / 2 + pad, y + h_ / 2 + pad)
            probe = Image.new("L", (GW, GH), 0)
            ImageDraw.Draw(probe).rectangle([box[0] / GS, box[1] / GS, box[2] / GS, box[3] / GS], fill=255)
            if not (np.asarray(occ, bool) & np.asarray(probe, bool)).any():
                reserve(box)
                return x, y
        return None

    for _ in range(int(110 * A)):
        w_, h_ = ctx.u(random.uniform(18, 36)), ctx.u(random.uniform(8, 13))
        if random.random() < 0.5:
            w_, h_ = h_, w_
        spot = free_spot(w_, h_, ctx.u(10))
        if not spot:
            continue
        x, y = spot
        col = p["primary_dim"] if random.random() < 0.62 else p["accent_dim"]
        d_soft.rectangle([(x - w_ / 2) * S, (y - h_ / 2) * S, (x + w_ / 2) * S, (y + h_ / 2) * S],
                         outline=mul(col, random.uniform(0.9, 1.5)),
                         width=max(1, int(ctx.s(ctx.u(1.8)))))

    for _ in range(int(150 * A)):
        spot = free_spot(ctx.u(9), ctx.u(9), ctx.u(4))
        if not spot:
            continue
        x, y = spot
        r = ctx.u(random.uniform(2.2, 4.6))
        col = random.choice([p["primary"], p["primary"], p["primary"],
                             p["accent"], p["spark"], p["rare"]])
        d_hot.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S],
                      fill=mul(col, random.uniform(0.45, 1.0)))

    # wordmark
    mark = ctx.layer()
    if a.mark and mk_box:
        dm = ImageDraw.Draw(mark)
        fm = font("sans_b", ctx.u(58) * S)
        fs = font("mono_b", ctx.u(19) * S)
        mx, my = mk_box[0] * S, mk_box[1] * S
        dm.text((mx, my), a.mark, font=fm, fill=mul(p["primary"], .82))
        bb = dm.textbbox((mx, my), a.mark, font=fm)
        dm.line([(mx, bb[3] + ctx.u(18) * S), (bb[2], bb[3] + ctx.u(18) * S)],
                fill=mul(p["accent"], .70), width=max(1, int(ctx.s(ctx.u(2)))))
        if a.submark:
            dm.text((mx + ctx.u(2) * S, bb[3] + ctx.u(32) * S), a.submark, font=fs,
                    fill=mul(p["accent"], .58))
        bx0, by0 = mx - ctx.u(24) * S, my - ctx.u(22) * S
        bx1, by1 = bb[2] + ctx.u(24) * S, bb[3] + ctx.u(74) * S
        armx, army = ctx.u(46) * S, ctx.u(34) * S
        bwid = max(1, int(ctx.s(ctx.u(2.2))))
        brk = mul(p["primary"], .45)
        for (cx_, cy_, sx_, sy_) in ((bx0, by0, 1, 1), (bx1, by0, -1, 1),
                                     (bx0, by1, 1, -1), (bx1, by1, -1, -1)):
            dm.line([(cx_, cy_), (cx_ + armx * sx_, cy_)], fill=brk, width=bwid)
            dm.line([(cx_, cy_), (cx_, cy_ + army * sy_)], fill=brk, width=bwid)

    out = base_gradient(ctx, (hx, hy), (0.12, 0.92))
    out += down(ctx, soft) * 0.95
    out += glow(ctx, soft, 6, 0.42)
    out += glow(ctx, soft, 20, 0.22)
    out += down(ctx, hot) * 1.00
    out += glow(ctx, hot, 3.5, 0.80)
    out += glow(ctx, hot, 13, 0.50)
    out += glow(ctx, hot, 40, 0.28)
    out += down(ctx, mark) * 0.95
    out += glow(ctx, mark, 9, 0.35)
    return finish(ctx, out, 0.44)

# ============================================================ style: coderain
KATA = [chr(c) for c in range(0x30A1, 0x30FA)]
LATG = list("0123456789<>[]{}/\\|=+*#$%&@ABCDEFGHIJKLMNPQRSTUVWXYZ")

def render_coderain(ctx, a):
    W, H, p = ctx.W, ctx.H, ctx.pal
    head_col = p["spark"]

    def pick():
        use_kata = HAS_CJK and a.glyphs != "ascii" and random.random() < 0.62
        return random.choice(KATA) if use_kata else random.choice(LATG)

    def plane(size, columns, tail, bright, head_frac, jitter=0.0):
        lay = Image.new("RGB", (W, H), (0, 0, 0))
        d = ImageDraw.Draw(lay)
        fk, fl = font("cjk", size), font("mono_b", size * 0.92)
        step = int(size * 1.16)
        for _ in range(columns):
            x = random.uniform(-size, W + size)
            n = random.randint(*tail)
            head_y = random.uniform(-H * 0.5, H * 1.35)
            side = ctx.quiet(x, head_y) * 0.6 + 0.4
            for j in range(n):
                y = head_y - j * step
                if y < -size or y > H:
                    continue
                t = j / max(1, n - 1)
                fade = (1.0 - t) ** 1.55
                if random.random() < 0.10:
                    fade *= random.uniform(0.2, 0.6)
                if j == 0 and random.random() < head_frac:
                    col, f = head_col, 1.0
                else:
                    col = p["primary"] if fade > 0.45 else p["primary_dim"]
                    f = fade
                f *= bright * side
                if f < 0.03:
                    continue
                ch = pick()
                fnt = fk if ord(ch) > 0x3000 else fl
                xx = x + (random.uniform(-jitter, jitter) if jitter else 0)
                d.text((xx, y), ch, font=fnt, fill=mul(col, f))
        return lay

    # columns scale with how many glyph-widths fit across the canvas, and tails
    # with how many glyph-heights fit down it, so density holds at any aspect
    cw = max(0.35, (W / 2560.0) / ctx.U)
    tl = max(0.5, (H / 1440.0) / ctx.U)
    T = lambda lo, hi: (max(3, int(lo * tl)), max(5, int(hi * tl)))
    far  = plane(ctx.u(15), int(150 * cw), T(14, 40), 0.34, 0.22)
    mid  = plane(ctx.u(26), int(105 * cw), T(10, 30), 0.88, 0.62)
    hero = plane(ctx.u(30), int(26 * cw),  T(6, 20),  1.55, 1.00)
    near = plane(ctx.u(58), int(14 * cw),  T(4, 12),  0.70, 0.45, jitter=ctx.u(1.5))

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
    return finish(ctx, out, 0.50)

# ============================================================ style: terminal
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

def render_terminal(ctx, a):
    W, H, p, S = ctx.W, ctx.H, ctx.pal, ctx.S
    rows = parse_session(a.session_text)
    prompt = f"{a.user}:~$ "
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
    tt = a.title or f"bash — {a.user}"
    dt.text((TX + body_w / 2 - dt.textlength(tt, font=ft) / 2, TY + TITLE / 2 - FS * 0.33 * S),
            tt, font=ft, fill=mul(p["primary"], 0.34))

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
            x = put(x0, yy, a.user, p["primary"], True)
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
    return finish(ctx, out, 0.48)

# =========================================================== style: codeblock
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

def render_codeblock(ctx, a):
    W, H, p, S = ctx.W, ctx.H, ctx.pal, ctx.S
    lines = a.code_text.rstrip("\n").split("\n")
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

    if a.gutter:
        fnum = font("mono", FS * 0.34 * S)
        for i in range(nrows):
            d.text((X0 - FS * 0.9 * S, Y0 + i * LH + FS * 0.30 * S), f"{i + 1:>2}",
                   font=fnum, fill=mul(p["primary"], 0.22))
        d.line([(X0 - FS * 0.36 * S, Y0 - FS * 0.16 * S),
                (X0 - FS * 0.36 * S, Y0 + text_h - LH * 0.28)],
               fill=mul(p["primary"], 0.16), width=max(1, int(ctx.s(ctx.u(2)))))

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

    if a.caption:
        fcap = font("mono", FS * 0.33 * S)
        d.text((X0, Y0 + text_h + FS * 0.38 * S), a.caption, font=fcap,
               fill=mul(p["primary"], 0.28))
    if a.cursor:
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
    return finish(ctx, out, 0.50)

# ----------------------------------------------------------------- cli
STYLES = {"pcb": render_pcb, "coderain": render_coderain,
          "terminal": render_terminal, "codeblock": render_codeblock}

def parse_size(s):
    if s in SIZES:
        return SIZES[s]
    m = re.fullmatch(r"(\d{3,5})\s*[xX×]\s*(\d{3,5})", s.strip())
    if not m:
        raise argparse.ArgumentTypeError(
            f"size must be WxH or one of: {', '.join(sorted(SIZES))}")
    return int(m.group(1)), int(m.group(2))

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="print presets and palettes, then exit")
    ap.add_argument("--style", choices=sorted(STYLES))
    ap.add_argument("--size", default="1440p", help="WxH, or a preset name")
    ap.add_argument("--palette", default="cyber", choices=sorted(PALETTES))
    ap.add_argument("--seed", type=int, default=None, help="omit for a random layout")
    ap.add_argument("--out", default=None)
    ap.add_argument("--quiet-zone", default="left",
                    choices=["left", "right", "top", "bottom", "none"],
                    help="edge kept darker so desktop icons stay readable")
    # pcb
    ap.add_argument("--mark", default="", help="wordmark text, e.g. 'J A M I E' (pcb)")
    ap.add_argument("--submark", default="", help="small line under the wordmark (pcb)")
    ap.add_argument("--chip-label", default="", help="text on the hero chip (pcb)")
    # coderain
    ap.add_argument("--glyphs", default="mixed", choices=["mixed", "ascii"])
    # terminal
    ap.add_argument("--user", default="you@localhost", help="shell prompt name (terminal)")
    ap.add_argument("--title", default="", help="window title bar text (terminal)")
    ap.add_argument("--script", default=None, help="session file (terminal)")
    # codeblock
    ap.add_argument("--code", default=None, help="code file (codeblock)")
    ap.add_argument("--caption", default="", help="small line under the code (codeblock)")
    ap.add_argument("--no-gutter", dest="gutter", action="store_false")
    ap.add_argument("--no-cursor", dest="cursor", action="store_false")
    a = ap.parse_args()

    if a.list:
        print("SIZES")
        for k, (w, h) in sorted(SIZES.items(), key=lambda kv: -kv[1][0] * kv[1][1]):
            print(f"  {k:<15} {w}x{h}  ({w/h:.2f}:1)")
        print("\nPALETTES\n  " + "  ".join(sorted(PALETTES)))
        print("\nSTYLES\n  " + "  ".join(sorted(STYLES)))
        return 0
    if not a.style:
        ap.error("--style is required (or use --list)")

    a.W, a.H = parse_size(a.size)
    if a.seed is None:
        a.seed = random.randrange(1, 10 ** 6)
    a.session_text = open(a.script).read() if a.script else DEFAULT_SESSION
    a.code_text = open(a.code).read() if a.code else DEFAULT_CODE

    ctx = Ctx(a)
    img = STYLES[a.style](ctx, a)
    out = a.out or f"wallpaper-{a.style}-{a.W}x{a.H}-{a.seed}.png"
    img.save(out, optimize=True)
    print(f"{out}  {a.W}x{a.H}  style={a.style} palette={a.palette} seed={a.seed}")
    return 0

if __name__ == "__main__":
    sys.exit(main())