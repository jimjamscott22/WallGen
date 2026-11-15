from __future__ import annotations

from PIL import Image, ImageDraw

from wallgen.engine.common import base_gradient, down, finish, mul
from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec
from wallgen.engine.styles.blueprint_subjects import SUBJECTS, Pen


def render_blueprint(ctx: Ctx, spec: RenderSpec, progress) -> Image.Image:
    palette = ctx.pal
    layer = ctx.layer()
    draw = ImageDraw.Draw(layer)
    width, height = layer.size
    unit = ctx.s(ctx.u(1))
    ink = palette["primary"]
    if spec.blueprint_grid:
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
    pen = Pen(draw, fx * width, fy * height, unit, palette,
              lettering=25 * unit / ctx.S >= 5)

    draw_subject, title = SUBJECTS[spec.blueprint_subject]
    draw_subject(pen, ctx.rng, spec.blueprint_dimensions)
    progress(0.65, f"drawing {title.lower()}")

    if spec.blueprint_labels:
        pen.title_block(title, "FRONT VIEW / A")
    progress(0.88, "compositing blueprint")

    out = base_gradient(ctx, (fx, fy))
    out += down(ctx, layer)
    return finish(ctx, out, 0.27)
