from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image

from wallgen.engine.spec import PALETTES, RenderSpec


class Ctx:
    """Everything a style needs: canvas size, scale, palette, safe zone, rng."""

    def __init__(self, spec: RenderSpec) -> None:
        self.W, self.H = spec.width, spec.height
        self.pal = PALETTES[spec.palette]
        self.seed = spec.seed
        self.zone = spec.quiet_zone
        # one "unit" == 1px at 1440p; every hand-tuned constant is in units
        self.U = min(self.W, self.H) / 1440.0
        # supersample as much as the pixel budget allows
        self.S = max(1.0, min(2.0, math.sqrt(24e6 / (self.W * self.H))))
        self.area = (self.W * self.H) / (2560 * 1440)
        self.portrait = self.H > self.W
        self.rng = random.Random(spec.seed)

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
