from __future__ import annotations

from math import cos, sin, tau

from PIL import Image, ImageDraw

from wallgen.engine.common import base_gradient, down, finish, font, mul
from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec


def render_blueprint(ctx: Ctx, spec: RenderSpec, progress) -> Image.Image:
    palette = ctx.pal
    layer = ctx.layer()
    draw = ImageDraw.Draw(layer)
    width, height = layer.size
    unit = ctx.s(ctx.u(1))
    ink = palette["primary"]
    grid = max(1, round(40 * unit))
    for axis, extent in enumerate((width, height)):
        for index, position in enumerate(range(extent // 2 % grid, extent, grid)):
            center_index = (extent // 2) // grid
            strength = 0.15 if (index - center_index) % 5 == 0 else 0.065
            if axis == 0:
                points = [(position, 0), (position, height)]
                quiet = ctx.quiet(position / ctx.S, ctx.H / 2)
            else:
                points = [(0, position), (width, position)]
                quiet = ctx.quiet(ctx.W / 2, position / ctx.S)
            draw.line(points, fill=mul(ink, strength * (0.5 + 0.5 * quiet)))
    progress(0.25, "drawing drafting grid")

    fx, fy = 0.5, 0.5
    if spec.blueprint_layout == "offset":
        fx, fy = {
            "left": (0.66, 0.5), "right": (0.34, 0.5),
            "top": (0.5, 0.66), "bottom": (0.5, 0.34),
            "none": (0.5, 0.66) if ctx.portrait else (0.66, 0.5),
        }[ctx.zone]
        unit *= 0.72
    cx, cy = fx * width, fy * height
    fine = mul(ink, 0.36)
    main = mul(ink, 0.86)
    accent = mul(palette["accent"], 0.78)

    def point(x, y):
        return cx + x * unit, cy + y * unit

    def line(points, color, weight=2):
        draw.line([point(x, y) for x, y in points], fill=color,
                  width=max(1, round(weight * unit)))

    def circle(x, y, radius, color, weight=2):
        draw.ellipse([point(x - radius, y - radius), point(x + radius, y + radius)],
                     outline=color, width=max(1, round(weight * unit)))

    # Orthographic front view of a seeded flange assembly.
    radius = ctx.rng.randint(252, 286)
    bore = ctx.rng.randint(83, 115)
    holes = ctx.rng.choice((6, 8, 10))
    bolt_circle = radius * 0.79
    phase = ctx.rng.uniform(0, tau / holes)
    for start in range(-360, 361, 24):
        line([(start, 0), (start + 12, 0)], fine)
        line([(0, start), (0, start + 12)], fine)
    for ring, color, weight in ((radius, main, 4), (radius - 14, fine, 2),
                                (bore + 28, main, 3), (bore, main, 4)):
        circle(0, 0, ring, color, weight)
    for index in range(holes):
        angle = phase + index * tau / holes
        x, y = bolt_circle * cos(angle), bolt_circle * sin(angle)
        circle(x, y, 24, fine)
        circle(x, y, 14, main, 3)
    progress(0.65, "drawing flange assembly")

    for edge in (-radius, radius):
        line([(edge, -48), (edge, -365)], fine)
        line([(edge - 9, -374), (edge + 9, -356)], accent, 3)
    line([(-radius, -365), (radius, -365)], accent)
    leader_angle = phase - tau / holes
    leader_x = bolt_circle * cos(leader_angle)
    leader_y = bolt_circle * sin(leader_angle)
    line([(leader_x, leader_y), (342, -156), (484, -156)], accent)
    line([(-bore * 0.7, bore * 0.7), (-300, 232), (-479, 232)], accent)
    line([(-479, 362), (479, 362)], fine)

    # Tiny custom renders have room for linework but no legible lettering.
    if 25 * unit / ctx.S >= 5:
        label_font = font("mono", 25 * unit)
        title_font = font("mono_b", 35 * unit)
        draw.text(point(0, -384), f"OD {radius * 2 / 5:.1f} mm", font=label_font,
                  fill=main, anchor="ms")
        draw.text(point(484, -172), f"{holes}x BOLT HOLES", font=label_font,
                  fill=main, anchor="rs")
        draw.text(point(-479, 215), f"BORE {bore * 2 / 5:.1f} mm", font=label_font,
                  fill=main, anchor="ls")
        draw.text(point(-479, 387), "FLANGE ASSEMBLY", font=title_font,
                  fill=main, anchor="lt")
        draw.text(point(479, 387), "FRONT VIEW / A", font=label_font,
                  fill=fine, anchor="rt")
    progress(0.88, "compositing blueprint")

    out = base_gradient(ctx, (fx, fy))
    out += down(ctx, layer)
    return finish(ctx, out, 0.27)
