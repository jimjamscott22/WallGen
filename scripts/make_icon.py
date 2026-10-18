"""Draw WallGen's app icon: a copper chip with verdigris traces on charcoal.

Writes src/wallgen/assets/wallgen.ico (every size Windows asks for) and a
256px PNG preview. Deterministic, so re-running it only changes the files
when this script changes.

    uv run python scripts/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from wallgen.ui import theme

SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
SUPERSAMPLE = 8
ASSETS = Path(__file__).resolve().parents[1] / "src" / "wallgen" / "assets"


def _draw(size: int) -> Image.Image:
    """One icon size. Below 32px the pins and traces would only be mush."""
    canvas = size * SUPERSAMPLE
    u = canvas / 16  # the design is laid out on a 16 x 16 grid
    detailed = size >= 32
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def box(x0, y0, x1, y1):
        return [round(x0 * u), round(y0 * u), round(x1 * u) - 1, round(y1 * u) - 1]

    draw.rounded_rectangle(box(0, 0, 16, 16), radius=round(3 * u), fill=theme.BG_WINDOW,
                           outline=theme.HAIRLINE, width=max(1, round(0.35 * u)))

    chip = (4.5, 4.5, 11.5, 11.5) if detailed else (3, 3, 13, 13)
    if detailed:
        trace = max(1, round(0.6 * u))
        # Two traces leave the chip and end in solder pads, like the PCB style.
        for points, pad in (
            ([(11.5, 6), (13, 6), (13, 2.8)], (13, 2.8)),
            ([(4.5, 10), (3, 10), (3, 13.2)], (3, 13.2)),
        ):
            draw.line([(x * u, y * u) for x, y in points], fill=theme.VERDIGRIS, width=trace, joint="curve")
            r = 0.85 * u
            draw.ellipse([pad[0] * u - r, pad[1] * u - r, pad[0] * u + r, pad[1] * u + r], fill=theme.VERDIGRIS)
        # Pins: three per side, in light copper.
        x0, y0, x1, y1 = chip
        for offset in (6.2, 8, 9.8):
            draw.rectangle(box(offset - 0.45, y0 - 1.1, offset + 0.45, y0), fill=theme.COPPER_LIGHT)
            draw.rectangle(box(offset - 0.45, y1, offset + 0.45, y1 + 1.1), fill=theme.COPPER_LIGHT)
            draw.rectangle(box(x0 - 1.1, offset - 0.45, x0, offset + 0.45), fill=theme.COPPER_LIGHT)
            draw.rectangle(box(x1, offset - 0.45, x1 + 1.1, offset + 0.45), fill=theme.COPPER_LIGHT)

    draw.rounded_rectangle(box(*chip), radius=round(0.8 * u), fill=theme.COPPER)
    x0, y0, x1, y1 = chip
    inset = 1.2 if detailed else 1.6
    draw.rounded_rectangle(box(x0 + inset, y0 + inset, x1 - inset, y1 - inset),
                           radius=round(0.5 * u), fill=theme.COPPER_DARK)
    # The power LED, as on the window's header.
    led = (x1 - inset - 1.3, y0 + inset + 1.3)
    r = (0.75 if detailed else 1.1) * u
    draw.ellipse([led[0] * u - r, led[1] * u - r, led[0] * u + r, led[1] * u + r], fill=theme.VERDIGRIS)

    return image.resize((size, size), Image.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    images = [_draw(size) for size in SIZES]
    largest = images[-1]
    largest.save(ASSETS / "wallgen.ico", format="ICO", sizes=[(s, s) for s in SIZES],
                 append_images=images[:-1])
    largest.save(ASSETS / "wallgen.png")
    print(f"Wrote {ASSETS / 'wallgen.ico'} ({', '.join(map(str, SIZES))} px)")


if __name__ == "__main__":
    main()
