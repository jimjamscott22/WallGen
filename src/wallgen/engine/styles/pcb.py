from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from wallgen.engine.common import base_gradient, down, finish, font, glow, mul
from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec

DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]


def render_pcb(ctx: Ctx, spec: RenderSpec, progress) -> Image.Image:
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
        d = ctx.rng.randrange(8)
        if ctx.rng.random() > diag_bias:
            d = (d // 2) * 2
        pts = [(x, y)]
        for _ in range(steps):
            if ctx.rng.random() < 0.88:
                d = (d + ctx.rng.choice([-1, 1])) % 8
                if ctx.rng.random() > diag_bias and d % 2 == 1:
                    d = (d + ctx.rng.choice([-1, 1])) % 8
            dx, dy = DIRS[d]
            L = ctx.rng.randint(*seglen)
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
    chip(HCX, HCY, hero, hero, 13, p["primary"], p["primary"], label=spec.chip_label)
    for fx, fy, fw, fh, pins, col, gl, four in [
        (0.885, 0.735, 210, 132, 7, p["accent"], p["spark"], False),
        (0.360, 0.780, 176, 112, 6, p["accent"], p["accent"], False),
        (0.845, 0.180, 150, 150, 6, p["primary"], p["primary"], True),
        (0.480, 0.150, 132, 90,  5, p["primary"], p["primary"], False)]:
        chip(W * fx, H * fy, ctx.u(fw), ctx.u(fh), pins, col, gl, four_side=four)
    progress(0.15, "placing chips")

    # wordmark keep-out
    mk_box = None
    if spec.mark:
        fm = font("sans_b", ctx.u(58) * S)
        tmp = ImageDraw.Draw(Image.new("L", (8, 8)))
        tw = tmp.textlength(spec.mark, font=fm) / S
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
            x = ctx.rng.uniform(-ctx.u(100), W + ctx.u(100))
            y = ctx.rng.uniform(-ctx.u(100), H + ctx.u(100))
            if ctx.rng.random() > ctx.quiet(x, y) * dens:
                continue
            pts = try_route(gen_path(x, y, ctx.rng.randint(*steps), seglen), clearance)
            if pts is None:
                continue
            placed += 1
            col, f = colf()
            d_soft.line(sc(pts), fill=mul(col, f), width=max(1, int(ctx.s(width))), joint="curve")
            if ctx.rng.random() < hot_frac:
                d_hot.line(sc(pts), fill=mul(col, min(1.0, f * 1.5)),
                           width=max(1, int(ctx.s(width * 0.42))), joint="curve")
            for (vx, vy) in (pts[0], pts[-1]):
                if 0 < vx < W and 0 < vy < H and ctx.rng.random() < 0.5:
                    r = ctx.u(ctx.rng.uniform(4, 8))
                    d_soft.ellipse([(vx - r) * S, (vy - r) * S, (vx + r) * S, (vy + r) * S],
                                   outline=mul(col, f * 0.9), width=max(1, int(ctx.s(ctx.u(1.8)))))
        return placed

    A = ctx.area
    seg = lambda lo, hi: (int(ctx.u(lo)), int(ctx.u(hi)))
    scatter(int(34 * A), int(900 * A), (4, 9), seg(100, 250), ctx.u(13), ctx.u(3.6),
            lambda: ((p["primary"] if ctx.rng.random() < .62 else p["accent"]),
                     ctx.rng.uniform(.70, .95)), 0.95)
    scatter(int(120 * A), int(3000 * A), (3, 8), seg(70, 240), ctx.u(10), ctx.u(2.7),
            lambda: ((p["primary"] if ctx.rng.random() < .70 else p["accent"]),
                     ctx.rng.uniform(.34, .58)), 0.35)
    scatter(int(340 * A), int(7000 * A), (2, 6), seg(40, 160), ctx.u(7), ctx.u(1.9),
            lambda: ((p["primary_dim"] if ctx.rng.random() < .74 else p["accent_dim"]),
                     ctx.rng.uniform(.55, .95)), 0.10)
    progress(0.5, "routing traces")

    for i in range(int(26 * max(1.0, A ** 0.5))):
        ang = ctx.rng.uniform(0, math.tau)
        r0 = hero * 0.61
        pts = try_route(gen_path(HCX + math.cos(ang) * r0, HCY + math.sin(ang) * r0,
                                 ctx.rng.randint(3, 7), seg(90, 260)), ctx.u(12))
        if pts is None:
            continue
        col = p["primary"] if i % 3 else p["accent"]
        d_soft.line(sc(pts), fill=mul(col, .72), width=max(1, int(ctx.s(ctx.u(3.2)))), joint="curve")
        d_hot.line(sc(pts), fill=col, width=max(1, int(ctx.s(ctx.u(1.4)))), joint="curve")

    def free_spot(w_, h_, pad):
        for _ in range(60):
            x, y = ctx.rng.uniform(0, W), ctx.rng.uniform(0, H)
            if ctx.rng.random() > ctx.quiet(x, y):
                continue
            box = (x - w_ / 2 - pad, y - h_ / 2 - pad, x + w_ / 2 + pad, y + h_ / 2 + pad)
            probe = Image.new("L", (GW, GH), 0)
            ImageDraw.Draw(probe).rectangle([box[0] / GS, box[1] / GS, box[2] / GS, box[3] / GS], fill=255)
            if not (np.asarray(occ, bool) & np.asarray(probe, bool)).any():
                reserve(box)
                return x, y
        return None

    for _ in range(int(110 * A)):
        w_, h_ = ctx.u(ctx.rng.uniform(18, 36)), ctx.u(ctx.rng.uniform(8, 13))
        if ctx.rng.random() < 0.5:
            w_, h_ = h_, w_
        spot = free_spot(w_, h_, ctx.u(10))
        if not spot:
            continue
        x, y = spot
        col = p["primary_dim"] if ctx.rng.random() < 0.62 else p["accent_dim"]
        d_soft.rectangle([(x - w_ / 2) * S, (y - h_ / 2) * S, (x + w_ / 2) * S, (y + h_ / 2) * S],
                         outline=mul(col, ctx.rng.uniform(0.9, 1.5)),
                         width=max(1, int(ctx.s(ctx.u(1.8)))))

    for _ in range(int(150 * A)):
        spot = free_spot(ctx.u(9), ctx.u(9), ctx.u(4))
        if not spot:
            continue
        x, y = spot
        r = ctx.u(ctx.rng.uniform(2.2, 4.6))
        col = ctx.rng.choice([p["primary"], p["primary"], p["primary"],
                             p["accent"], p["spark"], p["rare"]])
        d_hot.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S],
                      fill=mul(col, ctx.rng.uniform(0.45, 1.0)))
    progress(0.8, "adding silkscreen")

    # wordmark
    mark = ctx.layer()
    if spec.mark and mk_box:
        dm = ImageDraw.Draw(mark)
        fm = font("sans_b", ctx.u(58) * S)
        fs = font("mono_b", ctx.u(19) * S)
        mx, my = mk_box[0] * S, mk_box[1] * S
        dm.text((mx, my), spec.mark, font=fm, fill=mul(p["primary"], .82))
        bb = dm.textbbox((mx, my), spec.mark, font=fm)
        dm.line([(mx, bb[3] + ctx.u(18) * S), (bb[2], bb[3] + ctx.u(18) * S)],
                fill=mul(p["accent"], .70), width=max(1, int(ctx.s(ctx.u(2)))))
        if spec.submark:
            dm.text((mx + ctx.u(2) * S, bb[3] + ctx.u(32) * S), spec.submark, font=fs,
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

    progress(0.92, "compositing")
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
