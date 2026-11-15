from __future__ import annotations

from math import cos, sin, tau

from PIL import Image, ImageDraw

from wallgen.engine.common import base_gradient, down, finish, mul
from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec


def _ridge_points(level, phase, direction, portrait):
    points = []
    for sample in range(161):
        along = -0.08 + 1.16 * sample / 160
        wave = sin(tau * 1.25 * along + phase + 1.2 * level)
        across = (0.5 + direction * (along - 0.5) * 0.50
                  + level * (0.78 + 0.12 * cos(tau * along + phase))
                  + 0.085 * wave)
        points.append((across, along) if portrait else (along, across))
    return points


def _island_points(level, phase, second_phase, center, stretch):
    cx, cy = center
    rx, ry = stretch
    points = []
    for sample in range(180):
        angle = tau * sample / 180
        shape = 1 + 0.13 * cos(3 * angle + phase) + 0.075 * sin(5 * angle + second_phase)
        radius = level * shape
        points.append((cx + rx * radius * cos(angle), cy + ry * radius * sin(angle)))
    points.append(points[0])
    return points


def render_contour(ctx: Ctx, spec: RenderSpec, progress) -> Image.Image:
    palette = ctx.pal
    layer = ctx.layer()
    draw = ImageDraw.Draw(layer)
    width, height = layer.size
    phase = ctx.rng.uniform(0, tau)
    second_phase = ctx.rng.uniform(0, tau)
    direction = ctx.rng.choice((-1, 1))
    center = (ctx.rng.uniform(0.45, 0.55), ctx.rng.uniform(0.45, 0.55))
    short_side = min(width, height)
    stretch = (min(0.30, 0.66 * short_side / width),
               min(0.30, 0.66 * short_side / height))
    island = spec.contour_layout == "island"
    progress(0.18, "shaping terrain")

    # 6k+1 lines: the terrain keeps its shape and only the spacing changes, with
    # a major line every k-th and the accent line where it sits at k=5 (31 lines).
    k = {"few": 3, "normal": 5, "many": 7}[spec.contour_lines]
    accent_index = k if island else 3 * k
    for index in range(6 * k + 1):
        if island:
            points = _island_points(0.08 + 0.92 * index / (6 * k), phase, second_phase,
                                    center, stretch)
            prominence = 1 - (index * 5 / k) / 42
        else:
            level = (index - 3 * k) / (3 * k)
            points = _ridge_points(level, phase, direction, ctx.portrait)
            prominence = 1 - 0.55 * abs(level)

        major = index % k == 0
        accent = spec.contour_accent and index == accent_index
        color = palette["accent"] if accent else palette["primary"]
        strength = prominence * (0.82 if major else 0.43)
        weight = max(1, round(ctx.s(ctx.u(3.1 if major else 1.6))))
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            quiet = ctx.quiet((x1 + x2) * ctx.W / 2, (y1 + y2) * ctx.H / 2)
            ink = mul(color, strength * (0.46 + 0.54 * quiet))
            draw.line([(x1 * width, y1 * height), (x2 * width, y2 * height)],
                      fill=ink, width=weight)

    progress(0.80, "compositing contours")
    out = base_gradient(ctx, center, (0.35, 0.72))
    out += down(ctx, layer)
    return finish(ctx, out, 0.25)
