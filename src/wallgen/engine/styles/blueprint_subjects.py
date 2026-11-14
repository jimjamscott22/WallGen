"""The built-in Blueprint subjects: seeded orthographic front views.

A subject draws with a `Pen` in subject units around the sheet's focus point
and stays inside x ±480, y -390..340; the title block owns the space below.
Adding one means a draw function, a `SUBJECTS` entry and a `BlueprintSubject`
literal value in `engine/spec.py`.
"""
from __future__ import annotations

import random
from math import cos, sin, tau
from typing import Callable

from wallgen.engine.common import font, mul


class Pen:
    """Draws in subject units around the sheet's focus point."""

    def __init__(self, draw, cx: float, cy: float, unit: float, palette: dict,
                 lettering: bool) -> None:
        self._draw, self._cx, self._cy, self._unit = draw, cx, cy, unit
        self.fine = mul(palette["primary"], 0.36)
        self.main = mul(palette["primary"], 0.86)
        self.accent = mul(palette["accent"], 0.78)
        # Tiny renders have room for linework but no legible lettering.
        self.lettering = lettering
        self._fonts: dict = {}

    def _weight(self, weight) -> int:
        return max(1, round(weight * self._unit))

    def point(self, x, y) -> tuple[float, float]:
        return self._cx + x * self._unit, self._cy + y * self._unit

    def line(self, points, color, weight=2) -> None:
        self._draw.line([self.point(x, y) for x, y in points], fill=color,
                        width=self._weight(weight))

    def outline(self, points, color, weight=2) -> None:
        points = list(points)
        self.line(points + points[:1], color, weight)

    def circle(self, x, y, radius, color, weight=2) -> None:
        self._draw.ellipse([self.point(x - radius, y - radius),
                            self.point(x + radius, y + radius)],
                           outline=color, width=self._weight(weight))

    def text(self, x, y, text, color, *, size=25, bold=False, anchor="ms") -> None:
        if not self.lettering:
            return
        key = ("mono_b" if bold else "mono", size)
        if key not in self._fonts:
            self._fonts[key] = font(key[0], size * self._unit)
        self._draw.text(self.point(x, y), text, font=self._fonts[key], fill=color,
                        anchor=anchor)

    def title_block(self, title: str, caption: str) -> None:
        self.line([(-479, 362), (479, 362)], self.fine)
        self.text(-479, 387, title, self.main, size=35, bold=True, anchor="lt")
        self.text(479, 387, caption, self.fine, anchor="rt")


SubjectFn = Callable[[Pen, random.Random, bool], None]  # (pen, rng, dimensions)


def _centre_lines(pen: Pen) -> None:
    for start in range(-360, 361, 24):
        pen.line([(start, 0), (start + 12, 0)], pen.fine)
        pen.line([(0, start), (0, start + 12)], pen.fine)


def draw_flange(pen: Pen, rng: random.Random, dimensions: bool) -> None:
    radius = rng.randint(252, 286)
    bore = rng.randint(83, 115)
    holes = rng.choice((6, 8, 10))
    bolt_circle = radius * 0.79
    phase = rng.uniform(0, tau / holes)
    _centre_lines(pen)
    for ring, color, weight in ((radius, pen.main, 4), (radius - 14, pen.fine, 2),
                                (bore + 28, pen.main, 3), (bore, pen.main, 4)):
        pen.circle(0, 0, ring, color, weight)
    for index in range(holes):
        angle = phase + index * tau / holes
        x, y = bolt_circle * cos(angle), bolt_circle * sin(angle)
        pen.circle(x, y, 24, pen.fine)
        pen.circle(x, y, 14, pen.main, 3)
    if not dimensions:
        return

    for edge in (-radius, radius):
        pen.line([(edge, -48), (edge, -365)], pen.fine)
        pen.line([(edge - 9, -374), (edge + 9, -356)], pen.accent, 3)
    pen.line([(-radius, -365), (radius, -365)], pen.accent)
    leader_angle = phase - tau / holes
    leader_x = bolt_circle * cos(leader_angle)
    leader_y = bolt_circle * sin(leader_angle)
    pen.line([(leader_x, leader_y), (342, -156), (484, -156)], pen.accent)
    pen.line([(-bore * 0.7, bore * 0.7), (-300, 232), (-479, 232)], pen.accent)
    pen.text(0, -384, f"OD {radius * 2 / 5:.1f} mm", pen.main)
    pen.text(484, -172, f"{holes}x BOLT HOLES", pen.main, anchor="rs")
    pen.text(-479, 215, f"BORE {bore * 2 / 5:.1f} mm", pen.main, anchor="ls")


SUBJECTS: dict[str, tuple[SubjectFn, str]] = {
    "flange": (draw_flange, "FLANGE ASSEMBLY"),
}
