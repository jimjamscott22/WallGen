"""The built-in Blueprint subjects: seeded orthographic front views.

A subject draws with a `Pen` in subject units around the sheet's focus point
and stays inside x ±480, y -390..340; the title block owns the space below.
Adding one means a draw function, a `SUBJECTS` entry and a `BlueprintSubject`
literal value in `engine/spec.py`.
"""
from __future__ import annotations

import random
from math import asin, cos, pi, sin, tau
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


def _arc(cx, cy, radius, start, end, steps=12) -> list[tuple[float, float]]:
    return [(cx + radius * cos(start + (end - start) * i / steps),
             cy + radius * sin(start + (end - start) * i / steps)) for i in range(steps + 1)]


def _dashed_circle(pen: Pen, radius, color, dashes=48) -> None:
    for index in range(dashes):
        start = index * tau / dashes
        pen.line(_arc(0, 0, radius, start, start + tau / dashes / 2, 2), color)


def _diameter_dimension(pen: Pen, radius) -> None:
    """Outside-diameter dimension above a round part, as on the flange."""
    for edge in (-radius, radius):
        pen.line([(edge, -48), (edge, -365)], pen.fine)
        pen.line([(edge - 9, -374), (edge + 9, -356)], pen.accent, 3)
    pen.line([(-radius, -365), (radius, -365)], pen.accent)
    pen.text(0, -384, f"OD {radius * 2 / 5:.1f} mm", pen.main)


def _round_part_callouts(pen: Pen, bore, feature, note) -> None:
    """Leaders to a feature on the upper right and to the bore on the lower left."""
    pen.line([feature, (342, -156), (484, -156)], pen.accent)
    pen.line([(-bore * 0.7, bore * 0.7), (-300, 232), (-479, 232)], pen.accent)
    pen.text(484, -172, note, pen.main, anchor="rs")
    pen.text(-479, 215, f"BORE {bore * 2 / 5:.1f} mm", pen.main, anchor="ls")


def _nearest_step(target, phase, step) -> float:
    """The angle `phase + n * step` closest to `target`."""
    return phase + round((target - phase) / step) * step


def draw_gear(pen: Pen, rng: random.Random, dimensions: bool) -> None:
    teeth = rng.randint(14, 24)
    tip = rng.randint(250, 284)
    bore = rng.randint(50, 72)
    hub = bore + rng.randint(34, 48)
    holes = rng.choice((0, 4, 5, 6))
    pitch = tau / teeth
    phase = rng.uniform(0, pitch)
    module = 2 * tip / (teeth + 2)
    root = tip - 2.25 * module
    _centre_lines(pen)

    outline = []
    for index in range(teeth):
        start = phase + index * pitch
        for radius, part in ((root, 0.0), (root, 0.22), (tip, 0.36), (tip, 0.64), (root, 0.78)):
            angle = start + part * pitch
            outline.append((radius * cos(angle), radius * sin(angle)))
    pen.outline(outline, pen.main, 4)
    _dashed_circle(pen, tip - module, pen.fine)
    pen.circle(0, 0, root - 16, pen.fine)
    pen.circle(0, 0, hub, pen.main, 3)

    # Bore with a keyway cut into its top.
    key_half, key_depth = bore * 0.26, bore * 0.26
    gap = asin(key_half / bore)
    bore_outline = _arc(0, 0, bore, -pi / 2 + gap, 3 * pi / 2 - gap, 40)
    bore_outline += [(-key_half, -bore - key_depth), (key_half, -bore - key_depth)]
    pen.outline(bore_outline, pen.main, 4)

    if holes:
        ring = (hub + root - 16) / 2
        size = min((root - 16 - hub) * 0.30, ring * sin(pi / holes) * 0.62)
        hole_phase = phase + pi / holes
        for index in range(holes):
            angle = hole_phase + index * tau / holes
            pen.circle(ring * cos(angle), ring * sin(angle), size, pen.main, 3)
    if not dimensions:
        return

    _diameter_dimension(pen, tip)
    angle = _nearest_step(-0.5, phase + pitch / 2, pitch)
    _round_part_callouts(pen, bore, (tip * cos(angle), tip * sin(angle)), f"{teeth} TEETH")


def draw_bearing(pen: Pen, rng: random.Random, dimensions: bool) -> None:
    outer = rng.randint(250, 284)
    bore = rng.randint(96, 130)
    balls = rng.randint(8, 12)
    race = (outer - bore) * rng.uniform(0.21, 0.26)
    phase = rng.uniform(0, tau / balls)
    pitch_radius = (outer + bore) / 2
    ball = min((outer - bore - 2 * race) / 2 * 1.12, pitch_radius * sin(pi / balls) * 0.86)
    _centre_lines(pen)

    pen.circle(0, 0, outer, pen.main, 4)
    pen.circle(0, 0, outer - 12, pen.fine)
    pen.circle(0, 0, outer - race, pen.main, 3)
    pen.circle(0, 0, bore + race, pen.main, 3)
    pen.circle(0, 0, bore + 12, pen.fine)
    pen.circle(0, 0, bore, pen.main, 4)
    _dashed_circle(pen, pitch_radius, pen.fine)
    for index in range(balls):
        angle = phase + index * tau / balls
        x, y = pitch_radius * cos(angle), pitch_radius * sin(angle)
        pen.circle(x, y, ball, pen.main, 3)
        pen.circle(x, y, ball * 0.42, pen.fine)
    if not dimensions:
        return

    _diameter_dimension(pen, outer)
    angle = _nearest_step(-0.5, phase, tau / balls)
    feature = ((pitch_radius + ball) * cos(angle), (pitch_radius + ball) * sin(angle))
    _round_part_callouts(pen, bore, feature, f"{balls}x BALLS")


def draw_bracket(pen: Pen, rng: random.Random, dimensions: bool) -> None:
    half_w = rng.randint(330, 400)
    half_h = rng.randint(190, 240)
    corner = rng.randint(28, 48)
    holes = rng.choice((4, 6))
    slot_half = rng.randint(90, 160)
    slot_radius = rng.randint(34, 48)
    _centre_lines(pen)

    def plate(inset):
        w, h, r = half_w - inset, half_h - inset, corner - inset * 0.5
        return (_arc(w - r, -h + r, r, -pi / 2, 0, 8) + _arc(w - r, h - r, r, 0, pi / 2, 8)
                + _arc(-w + r, h - r, r, pi / 2, pi, 8) + _arc(-w + r, -h + r, r, pi, 3 * pi / 2, 8))

    pen.outline(plate(0), pen.main, 4)
    pen.outline(plate(14), pen.fine)
    slot = (_arc(slot_half, 0, slot_radius, -pi / 2, pi / 2, 16)
            + _arc(-slot_half, 0, slot_radius, pi / 2, 3 * pi / 2, 16))
    pen.outline(slot, pen.main, 4)

    hole_x, hole_y = half_w - corner - 26, half_h - corner - 26
    columns = (-hole_x, hole_x) if holes == 4 else (-hole_x, 0, hole_x)
    for x in columns:
        for y in (-hole_y, hole_y):
            pen.circle(x, y, 24, pen.fine)
            pen.circle(x, y, 14, pen.main, 3)
    if not dimensions:
        return

    # Width below the plate, height to its left, hole note above its top right.
    for edge in (-half_w, half_w):
        pen.line([(edge, half_h + 18), (edge, 326)], pen.fine)
        pen.line([(edge - 9, 309), (edge + 9, 327)], pen.accent, 3)
    pen.line([(-half_w, 318), (half_w, 318)], pen.accent)
    pen.text(-half_w / 2, 306, f"W {half_w * 2 / 5:.1f} mm", pen.main)  # clear of the centre line
    side = -half_w - 40
    for edge in (-half_h, half_h):
        pen.line([(-half_w - 18, edge), (side - 8, edge)], pen.fine)
        pen.line([(side - 9, edge + 9), (side + 9, edge - 9)], pen.accent, 3)
    pen.line([(side, -half_h), (side, half_h)], pen.accent)
    pen.text(-479, -half_h - 34, f"H {half_h * 2 / 5:.1f} mm", pen.main, anchor="ls")
    note_y = -half_h - 70
    pen.line([(hole_x, -hole_y), (hole_x + 44, note_y), (484, note_y)], pen.accent)
    pen.text(484, note_y - 16, f"{holes}x MOUNT HOLES", pen.main, anchor="rs")


SUBJECTS: dict[str, tuple[SubjectFn, str]] = {
    "flange": (draw_flange, "FLANGE ASSEMBLY"),
    "gear": (draw_gear, "SPUR GEAR"),
    "bearing": (draw_bearing, "BALL BEARING"),
    "bracket": (draw_bracket, "MOUNTING BRACKET"),
}
