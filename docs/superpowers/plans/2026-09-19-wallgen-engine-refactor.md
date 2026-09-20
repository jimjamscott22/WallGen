# WallGen Engine Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task (superpowers:executing-plans and superpowers:test-driven-development are disabled per this user's CLAUDE.md — write the implementation directly, then the test, then run it; skip the red/green ceremony). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the root-level `wallpaper.py` script into `src/wallgen/engine/`, a pure library with no argparse, no module-level RNG, and no import-time `sys.exit()` — matching the architecture the UI shell already assumes.

**Architecture:** A direct, mechanical file split of `wallpaper.py`'s existing sections (presets → `spec.py`, shared helpers → `common.py`, `Ctx` → `ctx.py`, each `render_*` → its own file under `styles/`), with five targeted fixes applied during the move: a `RenderSpec` dataclass instead of an argparse namespace, a per-instance RNG on `Ctx` instead of a global `random.seed()`, lazy non-fatal font resolution, an optional progress callback threaded through every style, and a `preview()` helper.

**Tech Stack:** Python 3.12, Pillow >= 11, NumPy >= 2, pytest (no Qt involved — the engine has zero UI dependencies).

**Spec:** [docs/wallgen-spec.md](../../wallgen-spec.md) §3, and the approved design: [docs/superpowers/specs/2026-09-19-wallgen-engine-refactor-design.md](../specs/2026-09-19-wallgen-engine-refactor-design.md).

## Global Constraints

- Python >= 3.12 (already set in `pyproject.toml`).
- Package management is `uv` only — `uv add`, `uv sync`, `uv run pytest`, never `pip`.
- Source layout is `src/wallgen/engine/...` per the spec's architecture (§2).
- The engine has **no** dependency on Qt or `win32` — `engine → nothing of ours`. Do not import PySide6 anywhere under `src/wallgen/engine/`.
- Every hand-tuned constant in the style renderers is copied byte-for-byte from `wallpaper.py`. This is a structural refactor: the only behavioral changes are the five listed in the design doc (RenderSpec, per-instance RNG, lazy fonts, progress callback, `preview()`). Do not "clean up" or re-tune anything else while moving code.
- `wallpaper.py` at the repo root is left untouched and unreferenced by the new code — do not delete or modify it in this plan.
- Out of scope (do not build in this plan): the `wallgen render` / `wallgen list` CLI, wiring the engine into the UI's `RenderJob`/`QThreadPool`, deleting `wallpaper.py`.

---

### Task 1: `engine/common.py` — shared helpers, lazy fonts, `EngineError`

**Files:**
- Modify: `pyproject.toml`
- Create: `src/wallgen/engine/__init__.py` (empty placeholder for now — filled in Task 8)
- Create: `src/wallgen/engine/common.py`
- Test: `tests/engine/test_common.py`

**Interfaces:**
- Consumes: nothing beyond Pillow/NumPy.
- Produces: `wallgen.engine.common.EngineError` (exception class), `C(*v) -> tuple`, `mul(c, f) -> tuple`, `font(key: str, size: float) -> ImageFont.FreeTypeFont` (raises `EngineError` if no monospace font is found), `has_cjk() -> bool`, `finish(ctx, out, extra_vignette=0.46) -> PIL.Image.Image`, `down(ctx, im) -> np.ndarray`, `glow(ctx, im, radius_units, gain) -> np.ndarray`, `base_gradient(ctx, focus=(0.66, 0.48), focus2=(0.12, 0.92)) -> np.ndarray`.

- [ ] **Step 1: Add Pillow and NumPy to `pyproject.toml`**

Modify the `dependencies` list in `pyproject.toml`:

```toml
dependencies = [
    "pyside6>=6.11",
    "pillow>=11",
    "numpy>=2",
]
```

- [ ] **Step 2: Sync the environment**

Run: `uv sync`
Expected: installs Pillow and NumPy into `.venv/`, updates `uv.lock`.

- [ ] **Step 3: Create the empty engine package marker**

`src/wallgen/engine/__init__.py`:

```python
```

(empty — filled in with the public API in Task 8)

- [ ] **Step 4: Write `src/wallgen/engine/common.py`**

This is `wallpaper.py` lines 38–39 (`C`), 75–103 (`FONT_CANDIDATES`/`FONTS`/`font`/`mul`), and 161–191 (`finish`/`down`/`glow`/`base_gradient`), with font resolution made lazy (spec §3.3) and Windows CJK font candidates added:

```python
from __future__ import annotations

import functools
import os

import numpy as np
from PIL import Image, ImageFilter, ImageFont


class EngineError(Exception):
    """Raised when the engine can't find a resource it needs to render."""


def C(*v):
    return tuple(v)


def mul(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


# Several candidates per role so the module survives a different font set.
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
            "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
            "C:/Windows/Fonts/YuGothR.ttc",
            "C:/Windows/Fonts/meiryo.ttc",
            "C:/Windows/Fonts/msgothic.ttc"],
}


@functools.lru_cache(maxsize=1)
def _resolve_fonts() -> dict[str, str | None]:
    fonts = {role: next((c for c in cands if os.path.exists(c)), None)
              for role, cands in FONT_CANDIDATES.items()}
    if not fonts["mono"]:
        raise EngineError("no monospace font found — install fonts-dejavu-core")
    fonts["mono_b"] = fonts["mono_b"] or fonts["mono"]
    fonts["sans_b"] = fonts["sans_b"] or fonts["mono_b"]
    return fonts


def has_cjk() -> bool:
    return _resolve_fonts()["cjk"] is not None


def font(key, size):
    fonts = _resolve_fonts()
    return ImageFont.truetype(fonts[key] or fonts["mono"], max(4, int(size)))


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
```

- [ ] **Step 5: Write `tests/engine/test_common.py`**

```python
import pytest

from wallgen.engine import common
from wallgen.engine.common import EngineError, font, has_cjk, mul


def test_mul_scales_and_clamps_channels():
    assert mul((100, 200, 250), 0.5) == (50, 100, 125)
    assert mul((100, 200, 250), 2.0) == (200, 255, 255)
    assert mul((100, 200, 250), -1.0) == (0, 0, 0)


def test_font_resolves_a_real_font():
    face = font("mono", 24)
    assert face is not None


def test_font_raises_engine_error_when_nothing_is_found(monkeypatch):
    common._resolve_fonts.cache_clear()
    monkeypatch.setitem(common.FONT_CANDIDATES, "mono", ["/no/such/font.ttf"])
    monkeypatch.setitem(common.FONT_CANDIDATES, "mono_b", [])
    monkeypatch.setitem(common.FONT_CANDIDATES, "sans_b", [])
    monkeypatch.setitem(common.FONT_CANDIDATES, "cjk", [])
    with pytest.raises(EngineError):
        font("mono", 24)
    common._resolve_fonts.cache_clear()


def test_has_cjk_returns_a_bool():
    assert isinstance(has_cjk(), bool)
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/engine/test_common.py -v`
Expected: PASS (4 tests). If `test_font_resolves_a_real_font` fails, the dev machine has none of the candidate font paths — check `common.FONT_CANDIDATES["mono"]` against what's actually installed under `C:/Windows/Fonts/`.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock src/wallgen/engine/__init__.py src/wallgen/engine/common.py tests/engine/test_common.py
git commit -m "feat: add wallgen.engine.common with lazy font resolution"
```

---

### Task 2: `engine/spec.py` — `RenderSpec`, `SIZES`, `PALETTES`

**Files:**
- Create: `src/wallgen/engine/spec.py`
- Test: `tests/engine/test_spec.py`

**Interfaces:**
- Consumes: `C` (Task 1, `wallgen.engine.common`).
- Produces: `Style` (`Literal["pcb", "coderain", "terminal", "codeblock"]`), `QuietZone` (`Literal["left", "right", "top", "bottom", "none"]`), `SIZES: dict[str, tuple[int, int]]`, `PALETTES: dict[str, dict[str, tuple[int, ...]]]`, `RenderSpec` dataclass with `.at(w: int, h: int) -> RenderSpec`.

- [ ] **Step 1: Write `src/wallgen/engine/spec.py`**

This is `wallpaper.py` lines 22–72 (`SIZES`, `PALETTES`) plus the `RenderSpec` dataclass from spec §3.1:

```python
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from wallgen.engine.common import C

Style = Literal["pcb", "coderain", "terminal", "codeblock"]
QuietZone = Literal["left", "right", "top", "bottom", "none"]

SIZES: dict[str, tuple[int, int]] = {
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

PALETTES: dict[str, dict[str, tuple[int, ...]]] = {
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


@dataclass(frozen=True, slots=True)
class RenderSpec:
    style: Style = "pcb"
    width: int = 2560
    height: int = 1440
    palette: str = "cyber"
    seed: int = 0
    quiet_zone: QuietZone = "left"
    mark: str = ""
    submark: str = ""
    chip_label: str = ""
    user: str = "you@localhost"
    title: str = ""
    session_text: str = ""
    code_text: str = ""
    caption: str = ""
    glyphs: Literal["mixed", "ascii"] = "mixed"
    gutter: bool = True
    cursor: bool = True

    def at(self, w: int, h: int) -> "RenderSpec":
        return replace(self, width=w, height=h)
```

- [ ] **Step 2: Write `tests/engine/test_spec.py`**

```python
from wallgen.engine.spec import PALETTES, SIZES, RenderSpec


def test_render_spec_defaults():
    spec = RenderSpec()
    assert spec.style == "pcb"
    assert (spec.width, spec.height) == (2560, 1440)
    assert spec.palette == "cyber"
    assert spec.quiet_zone == "left"
    assert spec.gutter is True
    assert spec.cursor is True


def test_at_returns_a_new_spec_with_only_size_changed():
    spec = RenderSpec(style="terminal", seed=42, palette="amber")
    resized = spec.at(3440, 1440)
    assert resized.width == 3440
    assert resized.height == 1440
    assert resized.style == "terminal"
    assert resized.seed == 42
    assert resized.palette == "amber"
    assert spec.width == 2560  # original untouched (frozen dataclass)


def test_sizes_and_palettes_cover_the_known_set():
    assert SIZES["1440p"] == (2560, 1440)
    assert SIZES["uw-1440"] == (3440, 1440)
    assert set(PALETTES) == {"cyber", "amber", "matrix", "violet", "ice", "crimson"}
    for palette in PALETTES.values():
        assert set(palette) == {
            "primary", "primary_dim", "accent", "accent_dim",
            "spark", "rare", "ok", "warn", "bg",
        }
```

- [ ] **Step 3: Run the tests**

Run: `uv run pytest tests/engine/test_spec.py -v`
Expected: PASS (3 tests)

- [ ] **Step 4: Commit**

```bash
git add src/wallgen/engine/spec.py tests/engine/test_spec.py
git commit -m "feat: add RenderSpec, SIZES, and PALETTES to wallgen.engine"
```

---

### Task 3: `engine/ctx.py` — `Ctx` with a per-instance RNG

**Files:**
- Create: `src/wallgen/engine/ctx.py`
- Test: `tests/engine/test_ctx.py`

**Interfaces:**
- Consumes: `RenderSpec`, `PALETTES` (Task 2).
- Produces: `Ctx(spec: RenderSpec)` with attributes `W, H, pal, seed, zone, U, S, area, portrait, rng: random.Random` and methods `.u(v)`, `.s(v)`, `.layer() -> PIL.Image.Image`, `.quiet(x, y) -> float`, `.quiet_mask() -> np.ndarray`.

- [ ] **Step 1: Write `src/wallgen/engine/ctx.py`**

This is `wallpaper.py` lines 105–159, with the constructor reading `spec.width`/`spec.height` instead of `a.W`/`a.H`, and the global `random.seed(self.seed)` replaced by a per-instance RNG (spec §3.2 — the fix for the concurrent-render corruption bug):

```python
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
```

- [ ] **Step 2: Write `tests/engine/test_ctx.py`**

```python
import random

from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec


def test_ctx_reads_size_and_palette_from_the_spec():
    ctx = Ctx(RenderSpec(width=1920, height=1080, palette="amber", quiet_zone="right"))
    assert (ctx.W, ctx.H) == (1920, 1080)
    assert ctx.pal["primary"] == (255, 168, 64)
    assert ctx.zone == "right"
    assert ctx.portrait is False


def test_ctx_rng_is_a_private_instance_seeded_reproducibly():
    ctx_a = Ctx(RenderSpec(seed=99))
    ctx_b = Ctx(RenderSpec(seed=99))
    assert isinstance(ctx_a.rng, random.Random)
    assert [ctx_a.rng.random() for _ in range(5)] == [ctx_b.rng.random() for _ in range(5)]


def test_ctx_rng_does_not_touch_the_global_random_module():
    before = random.getstate()
    Ctx(RenderSpec(seed=123)).rng.random()
    assert random.getstate() == before


def test_quiet_and_quiet_mask_stay_in_range():
    ctx = Ctx(RenderSpec(width=640, height=360, quiet_zone="left"))
    assert 0.0 <= ctx.quiet(0, 0) <= 1.0
    assert 0.0 <= ctx.quiet(640, 360) <= 1.0
    mask = ctx.quiet_mask()
    assert mask.shape == (360, 640)
    assert mask.min() >= 0.0
```

- [ ] **Step 3: Run the tests**

Run: `uv run pytest tests/engine/test_ctx.py -v`
Expected: PASS (4 tests)

- [ ] **Step 4: Commit**

```bash
git add src/wallgen/engine/ctx.py tests/engine/test_ctx.py
git commit -m "feat: add Ctx with a per-instance rng instead of global random.seed"
```

---

### Task 4: `engine/styles/pcb.py`

**Files:**
- Create: `src/wallgen/engine/styles/__init__.py`
- Create: `src/wallgen/engine/styles/pcb.py`
- Test: `tests/engine/test_style_pcb.py`

**Interfaces:**
- Consumes: `Ctx` (Task 3), `RenderSpec` (Task 2), `mul, font, finish, down, glow, base_gradient` (Task 1).
- Produces: `render_pcb(ctx: Ctx, spec: RenderSpec, progress) -> PIL.Image.Image`.

This is `wallpaper.py` lines 193–417 (the `DIRS` constant and `render_pcb`), mechanically transformed: the function's second parameter is renamed from `a` to `spec` (every `a.foo` becomes `spec.foo`), every `random.` call becomes `ctx.rng.`, and a `progress` parameter is added with four call sites per spec §3.4.

- [ ] **Step 1: Create `src/wallgen/engine/styles/__init__.py`**

```python
```

(empty — marks the package)

- [ ] **Step 2: Write `src/wallgen/engine/styles/pcb.py`**

```python
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
```

- [ ] **Step 3: Write `tests/engine/test_style_pcb.py`**

```python
from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec
from wallgen.engine.styles.pcb import render_pcb


def test_render_pcb_returns_correctly_sized_image():
    spec = RenderSpec(style="pcb", width=480, height=270, seed=1, mark="TEST")
    ctx = Ctx(spec)
    image = render_pcb(ctx, spec, lambda fraction, note: None)
    assert image.size == (480, 270)
    assert image.mode == "RGB"


def test_render_pcb_reports_monotonic_progress():
    calls = []
    spec = RenderSpec(style="pcb", width=480, height=270, seed=1)
    ctx = Ctx(spec)
    render_pcb(ctx, spec, lambda fraction, note: calls.append(fraction))
    assert len(calls) >= 3
    assert calls == sorted(calls)
    assert all(0.0 <= f <= 1.0 for f in calls)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/engine/test_style_pcb.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/wallgen/engine/styles/__init__.py src/wallgen/engine/styles/pcb.py tests/engine/test_style_pcb.py
git commit -m "feat: move render_pcb into wallgen.engine.styles"
```

---

### Task 5: `engine/styles/coderain.py`

**Files:**
- Create: `src/wallgen/engine/styles/coderain.py`
- Test: `tests/engine/test_style_coderain.py`

**Interfaces:**
- Consumes: `Ctx` (Task 3), `RenderSpec` (Task 2), `mul, font, finish, has_cjk` (Task 1).
- Produces: `render_coderain(ctx: Ctx, spec: RenderSpec, progress) -> PIL.Image.Image`.

This is `wallpaper.py` lines 419–490 (the `KATA`/`LATG` constants and `render_coderain`). The `HAS_CJK` module-level constant becomes the lazy `has_cjk()` call (consistent with making font resolution lazy in Task 1); `a.glyphs` becomes `spec.glyphs`; every `random.` call becomes `ctx.rng.`.

- [ ] **Step 1: Write `src/wallgen/engine/styles/coderain.py`**

```python
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from wallgen.engine.common import finish, font, has_cjk, mul
from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec

KATA = [chr(c) for c in range(0x30A1, 0x30FA)]
LATG = list("0123456789<>[]{}/\\|=+*#$%&@ABCDEFGHIJKLMNPQRSTUVWXYZ")


def render_coderain(ctx: Ctx, spec: RenderSpec, progress) -> Image.Image:
    W, H, p = ctx.W, ctx.H, ctx.pal
    head_col = p["spark"]

    def pick():
        use_kata = has_cjk() and spec.glyphs != "ascii" and ctx.rng.random() < 0.62
        return ctx.rng.choice(KATA) if use_kata else ctx.rng.choice(LATG)

    def plane(size, columns, tail, bright, head_frac, jitter=0.0):
        lay = Image.new("RGB", (W, H), (0, 0, 0))
        d = ImageDraw.Draw(lay)
        fk, fl = font("cjk", size), font("mono_b", size * 0.92)
        step = int(size * 1.16)
        for _ in range(columns):
            x = ctx.rng.uniform(-size, W + size)
            n = ctx.rng.randint(*tail)
            head_y = ctx.rng.uniform(-H * 0.5, H * 1.35)
            side = ctx.quiet(x, head_y) * 0.6 + 0.4
            for j in range(n):
                y = head_y - j * step
                if y < -size or y > H:
                    continue
                t = j / max(1, n - 1)
                fade = (1.0 - t) ** 1.55
                if ctx.rng.random() < 0.10:
                    fade *= ctx.rng.uniform(0.2, 0.6)
                if j == 0 and ctx.rng.random() < head_frac:
                    col, f = head_col, 1.0
                else:
                    col = p["primary"] if fade > 0.45 else p["primary_dim"]
                    f = fade
                f *= bright * side
                if f < 0.03:
                    continue
                ch = pick()
                fnt = fk if ord(ch) > 0x3000 else fl
                xx = x + (ctx.rng.uniform(-jitter, jitter) if jitter else 0)
                d.text((xx, y), ch, font=fnt, fill=mul(col, f))
        return lay

    progress(0.1, "rendering rain")

    # columns scale with how many glyph-widths fit across the canvas, and tails
    # with how many glyph-heights fit down it, so density holds at any aspect
    cw = max(0.35, (W / 2560.0) / ctx.U)
    tl = max(0.5, (H / 1440.0) / ctx.U)
    T = lambda lo, hi: (max(3, int(lo * tl)), max(5, int(hi * tl)))
    far  = plane(ctx.u(15), int(150 * cw), T(14, 40), 0.34, 0.22)
    mid  = plane(ctx.u(26), int(105 * cw), T(10, 30), 0.88, 0.62)
    hero = plane(ctx.u(30), int(26 * cw),  T(6, 20),  1.55, 1.00)
    near = plane(ctx.u(58), int(14 * cw),  T(4, 12),  0.70, 0.45, jitter=ctx.u(1.5))
    progress(0.6, "layering depth planes")

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
    progress(0.9, "compositing")
    return finish(ctx, out, 0.50)
```

- [ ] **Step 2: Write `tests/engine/test_style_coderain.py`**

```python
from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec
from wallgen.engine.styles.coderain import render_coderain


def test_render_coderain_returns_correctly_sized_image():
    spec = RenderSpec(style="coderain", width=480, height=270, seed=2)
    ctx = Ctx(spec)
    image = render_coderain(ctx, spec, lambda fraction, note: None)
    assert image.size == (480, 270)
    assert image.mode == "RGB"


def test_render_coderain_respects_ascii_only_glyphs():
    spec = RenderSpec(style="coderain", width=480, height=270, seed=2, glyphs="ascii")
    ctx = Ctx(spec)
    image = render_coderain(ctx, spec, lambda fraction, note: None)
    assert image.size == (480, 270)


def test_render_coderain_reports_monotonic_progress():
    calls = []
    spec = RenderSpec(style="coderain", width=480, height=270, seed=2)
    ctx = Ctx(spec)
    render_coderain(ctx, spec, lambda fraction, note: calls.append(fraction))
    assert len(calls) >= 3
    assert calls == sorted(calls)
```

- [ ] **Step 3: Run the tests**

Run: `uv run pytest tests/engine/test_style_coderain.py -v`
Expected: PASS (3 tests)

- [ ] **Step 4: Commit**

```bash
git add src/wallgen/engine/styles/coderain.py tests/engine/test_style_coderain.py
git commit -m "feat: move render_coderain into wallgen.engine.styles"
```

---

### Task 6: `engine/styles/terminal.py`

**Files:**
- Create: `src/wallgen/engine/styles/terminal.py`
- Test: `tests/engine/test_style_terminal.py`

**Interfaces:**
- Consumes: `Ctx` (Task 3), `RenderSpec` (Task 2), `C, mul, font, finish, down, glow, base_gradient` (Task 1).
- Produces: `render_terminal(ctx: Ctx, spec: RenderSpec, progress) -> PIL.Image.Image`, `parse_session(text: str) -> list[tuple[str, str]]`, `DEFAULT_SESSION: str`.

This is `wallpaper.py` lines 492–619 (`DEFAULT_SESSION`, `parse_session`, `render_terminal`). `render_terminal` has no `random.` calls, so only the `a` → `spec` rename applies. `spec.session_text` defaults to `""` in `RenderSpec` (Task 2), so the CLI's old fallback-to-`DEFAULT_SESSION` logic moves here.

- [ ] **Step 1: Write `src/wallgen/engine/styles/terminal.py`**

```python
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
```

- [ ] **Step 2: Write `tests/engine/test_style_terminal.py`**

```python
from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec
from wallgen.engine.styles.terminal import DEFAULT_SESSION, parse_session, render_terminal


def test_parse_session_recognizes_commands_status_and_output():
    rows = parse_session("$ ls\n[ok] done\nplain text\n")
    assert rows == [("cmd", "ls"), ("status:ok", "done"), ("out", "plain text")]


def test_render_terminal_falls_back_to_default_session_when_empty():
    spec = RenderSpec(style="terminal", width=480, height=270, seed=3, session_text="")
    ctx = Ctx(spec)
    image = render_terminal(ctx, spec, lambda fraction, note: None)
    assert image.size == (480, 270)
    assert parse_session(DEFAULT_SESSION)  # sanity: default text parses to something


def test_render_terminal_uses_custom_session_text():
    spec = RenderSpec(style="terminal", width=480, height=270, seed=3,
                       session_text="$ echo hi\nhi\n", user="me@box")
    ctx = Ctx(spec)
    image = render_terminal(ctx, spec, lambda fraction, note: None)
    assert image.size == (480, 270)


def test_render_terminal_reports_monotonic_progress():
    calls = []
    spec = RenderSpec(style="terminal", width=480, height=270, seed=3)
    ctx = Ctx(spec)
    render_terminal(ctx, spec, lambda fraction, note: calls.append(fraction))
    assert len(calls) >= 3
    assert calls == sorted(calls)
```

- [ ] **Step 3: Run the tests**

Run: `uv run pytest tests/engine/test_style_terminal.py -v`
Expected: PASS (4 tests)

- [ ] **Step 4: Commit**

```bash
git add src/wallgen/engine/styles/terminal.py tests/engine/test_style_terminal.py
git commit -m "feat: move render_terminal into wallgen.engine.styles"
```

---

### Task 7: `engine/styles/codeblock.py`

**Files:**
- Create: `src/wallgen/engine/styles/codeblock.py`
- Test: `tests/engine/test_style_codeblock.py`

**Interfaces:**
- Consumes: `Ctx` (Task 3), `RenderSpec` (Task 2), `C, mul, font, finish, down, glow, base_gradient` (Task 1).
- Produces: `render_codeblock(ctx: Ctx, spec: RenderSpec, progress) -> PIL.Image.Image`, `DEFAULT_CODE: str`.

This is `wallpaper.py` lines 621–733 (`DEFAULT_CODE`, `KEYWORDS`, `TOKEN_RE`, `render_codeblock`). No `random.` calls in this style. `spec.code_text` defaults to `""`, so the CLI's old fallback-to-`DEFAULT_CODE` logic moves here, same as Task 6's terminal fallback.

- [ ] **Step 1: Write `src/wallgen/engine/styles/codeblock.py`**

```python
from __future__ import annotations

import re

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from wallgen.engine.common import C, base_gradient, down, finish, font, glow, mul
from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec

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


def render_codeblock(ctx: Ctx, spec: RenderSpec, progress) -> Image.Image:
    W, H, p, S = ctx.W, ctx.H, ctx.pal, ctx.S
    lines = (spec.code_text or DEFAULT_CODE).rstrip("\n").split("\n")
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

    if spec.gutter:
        fnum = font("mono", FS * 0.34 * S)
        for i in range(nrows):
            d.text((X0 - FS * 0.9 * S, Y0 + i * LH + FS * 0.30 * S), f"{i + 1:>2}",
                   font=fnum, fill=mul(p["primary"], 0.22))
        d.line([(X0 - FS * 0.36 * S, Y0 - FS * 0.16 * S),
                (X0 - FS * 0.36 * S, Y0 + text_h - LH * 0.28)],
               fill=mul(p["primary"], 0.16), width=max(1, int(ctx.s(ctx.u(2)))))
    progress(0.3, "drawing gutter")

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
    progress(0.65, "highlighting syntax")

    if spec.caption:
        fcap = font("mono", FS * 0.33 * S)
        d.text((X0, Y0 + text_h + FS * 0.38 * S), spec.caption, font=fcap,
               fill=mul(p["primary"], 0.28))
    if spec.cursor:
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
    progress(0.9, "compositing")
    return finish(ctx, out, 0.50)
```

- [ ] **Step 2: Write `tests/engine/test_style_codeblock.py`**

```python
from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec
from wallgen.engine.styles.codeblock import DEFAULT_CODE, render_codeblock


def test_render_codeblock_falls_back_to_default_code_when_empty():
    spec = RenderSpec(style="codeblock", width=480, height=270, seed=4, code_text="")
    ctx = Ctx(spec)
    image = render_codeblock(ctx, spec, lambda fraction, note: None)
    assert image.size == (480, 270)
    assert DEFAULT_CODE.strip()


def test_render_codeblock_uses_custom_code_text():
    spec = RenderSpec(style="codeblock", width=480, height=270, seed=4,
                       code_text="def f(x):\n    return x + 1\n", caption="a note")
    ctx = Ctx(spec)
    image = render_codeblock(ctx, spec, lambda fraction, note: None)
    assert image.size == (480, 270)


def test_render_codeblock_reports_monotonic_progress():
    calls = []
    spec = RenderSpec(style="codeblock", width=480, height=270, seed=4)
    ctx = Ctx(spec)
    render_codeblock(ctx, spec, lambda fraction, note: calls.append(fraction))
    assert len(calls) >= 3
    assert calls == sorted(calls)
```

- [ ] **Step 3: Run the tests**

Run: `uv run pytest tests/engine/test_style_codeblock.py -v`
Expected: PASS (3 tests)

- [ ] **Step 4: Commit**

```bash
git add src/wallgen/engine/styles/codeblock.py tests/engine/test_style_codeblock.py
git commit -m "feat: move render_codeblock into wallgen.engine.styles"
```

---

### Task 8: `engine/__init__.py` — public API (`render`, `preview`)

**Files:**
- Modify: `src/wallgen/engine/__init__.py`
- Test: `tests/engine/test_engine_init.py`

**Interfaces:**
- Consumes: `RenderSpec` (Task 2), `Ctx` (Task 3), all four `render_*` functions (Tasks 4–7), `EngineError` (Task 1).
- Produces: `wallgen.engine.render(spec: RenderSpec, progress=None) -> PIL.Image.Image`, `wallgen.engine.preview(spec: RenderSpec, max_width: int = 1280, progress=None) -> PIL.Image.Image`, and re-exports `RenderSpec`, `EngineError`, `SIZES`, `PALETTES`.

- [ ] **Step 1: Write `src/wallgen/engine/__init__.py`**

```python
from __future__ import annotations

from typing import Callable

from PIL import Image

from wallgen.engine.common import EngineError
from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import PALETTES, SIZES, RenderSpec
from wallgen.engine.styles.codeblock import render_codeblock
from wallgen.engine.styles.coderain import render_coderain
from wallgen.engine.styles.pcb import render_pcb
from wallgen.engine.styles.terminal import render_terminal

__all__ = ["render", "preview", "RenderSpec", "EngineError", "SIZES", "PALETTES"]

ProgressFn = Callable[[float, str], None]

_STYLES = {
    "pcb": render_pcb,
    "coderain": render_coderain,
    "terminal": render_terminal,
    "codeblock": render_codeblock,
}


def render(spec: RenderSpec, progress: ProgressFn | None = None) -> Image.Image:
    on_progress = progress or (lambda fraction, note: None)
    on_progress(0.0, "starting")
    ctx = Ctx(spec)
    image = _STYLES[spec.style](ctx, spec, on_progress)
    on_progress(1.0, "done")
    return image


def preview(spec: RenderSpec, max_width: int = 1280, progress: ProgressFn | None = None) -> Image.Image:
    scale = min(1.0, max_width / spec.width)
    return render(spec.at(round(spec.width * scale), round(spec.height * scale)), progress=progress)
```

- [ ] **Step 2: Write `tests/engine/test_engine_init.py`**

```python
from wallgen.engine import EngineError, PALETTES, RenderSpec, SIZES, preview, render


def test_render_dispatches_to_the_requested_style():
    spec = RenderSpec(style="pcb", width=480, height=270, seed=2)
    image = render(spec)
    assert image.size == (480, 270)


def test_render_works_without_a_progress_callback():
    spec = RenderSpec(style="terminal", width=480, height=270, seed=2)
    image = render(spec)  # progress=None, must not raise
    assert image.size == (480, 270)


def test_preview_scales_down_and_preserves_aspect_ratio():
    spec = RenderSpec(style="terminal", width=2560, height=1440, seed=3)
    image = preview(spec, max_width=640)
    assert image.size == (640, 360)


def test_preview_does_not_upscale_when_already_smaller_than_max_width():
    spec = RenderSpec(style="pcb", width=480, height=270, seed=3)
    image = preview(spec, max_width=1280)
    assert image.size == (480, 270)


def test_render_calls_progress_from_start_to_done():
    calls = []
    spec = RenderSpec(style="codeblock", width=480, height=270, seed=4)
    render(spec, progress=lambda fraction, note: calls.append(fraction))
    assert calls[0] == 0.0
    assert calls[-1] == 1.0
    assert calls == sorted(calls)


def test_public_exports_are_importable():
    assert RenderSpec().style == "pcb"
    assert "cyber" in PALETTES
    assert "1440p" in SIZES
    assert issubclass(EngineError, Exception)
```

- [ ] **Step 3: Run the tests**

Run: `uv run pytest tests/engine/test_engine_init.py -v`
Expected: PASS (6 tests)

- [ ] **Step 4: Commit**

```bash
git add src/wallgen/engine/__init__.py tests/engine/test_engine_init.py
git commit -m "feat: expose render() and preview() as the engine's public API"
```

---

### Task 9: Determinism test (the fix this refactor exists for)

**Files:**
- Test: `tests/engine/test_determinism.py`

**Interfaces:**
- Consumes: `render`, `RenderSpec` (Task 8).
- Produces: nothing new — this task is pure verification of spec §3.2's fix.

This is the one test called out by both the spec and the design doc as load-bearing: it proves that replacing the global `random.seed()` with a per-instance `Ctx.rng` actually fixes the concurrent-render corruption bug, rather than just moving the bug around.

- [ ] **Step 1: Write `tests/engine/test_determinism.py`**

```python
from concurrent.futures import ThreadPoolExecutor

from wallgen.engine import RenderSpec, render


def test_render_is_deterministic_under_concurrency():
    spec = RenderSpec(style="pcb", width=640, height=360, seed=7)
    once = render(spec).tobytes()
    with ThreadPoolExecutor(4) as ex:
        results = [f.result().tobytes() for f in
                   [ex.submit(render, spec) for _ in range(4)]]
    assert all(r == once for r in results)
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/engine/test_determinism.py -v`
Expected: PASS. If this fails, some code path is still reading the global `random` module instead of `ctx.rng` — check `git grep "random\." src/wallgen/engine` for any call not prefixed with `ctx.rng.` (excluding `ctx.py`'s own `random.Random(...)` construction and `common.py`'s `np.random.default_rng(...)`, both of which are already per-call/per-instance and correct as-is).

- [ ] **Step 3: Commit**

```bash
git add tests/engine/test_determinism.py
git commit -m "test: verify renders are deterministic under concurrent execution"
```

---

### Task 10: Cross-style smoke tests via the public API

**Files:**
- Test: `tests/engine/test_render_smoke.py`

**Interfaces:**
- Consumes: `render`, `preview`, `RenderSpec` (Task 8).
- Produces: nothing new — final verification that all four styles work end-to-end through the public API (not just the direct per-style imports tested in Tasks 4–7).

- [ ] **Step 1: Write `tests/engine/test_render_smoke.py`**

```python
import pytest

from wallgen.engine import RenderSpec, preview, render

STYLES = ["pcb", "coderain", "terminal", "codeblock"]


@pytest.mark.parametrize("style", STYLES)
def test_render_produces_an_image_of_the_requested_size(style):
    spec = RenderSpec(style=style, width=480, height=270, seed=11)
    image = render(spec)
    assert image.size == (480, 270)
    assert image.mode == "RGB"


@pytest.mark.parametrize("style", STYLES)
def test_preview_is_never_wider_than_max_width(style):
    spec = RenderSpec(style=style, width=2560, height=1440, seed=12)
    image = preview(spec, max_width=640)
    assert image.width <= 640


@pytest.mark.parametrize("style", STYLES)
def test_same_seed_and_spec_produce_identical_bytes(style):
    spec = RenderSpec(style=style, width=480, height=270, seed=13)
    assert render(spec).tobytes() == render(spec).tobytes()
```

- [ ] **Step 2: Run the full engine test suite**

Run: `uv run pytest tests/engine/ -v`
Expected: every test across all `tests/engine/*.py` files PASSes (Tasks 1–10 combined).

- [ ] **Step 3: Run the full project test suite**

Run: `uv run pytest -v`
Expected: all engine tests pass, and all pre-existing UI tests (`tests/ui/`, `tests/test_main.py`) still pass unchanged — this task touches nothing under `src/wallgen/ui/`.

- [ ] **Step 4: Commit**

```bash
git add tests/engine/test_render_smoke.py
git commit -m "test: add cross-style smoke tests through the public render/preview API"
```

---

## After this plan

`from wallgen.engine import render, RenderSpec; render(RenderSpec()).save('x.png')` works for all four styles — Milestone 1 (spec §7) is done. What's still open, per the spec's build order:

- Milestone 2 (spec §6): wire `render()`/`preview()` into the UI via a `RenderJob`/`QThreadPool`, replacing the `.viewport` placeholder and `.style_panel` mock field values with real renders and real progress updates.
- The `wallgen render` / `wallgen list` CLI (spec §3, kept out of this plan's scope).
- Milestone 3 (spec §4): `SystemParametersInfoW` behind Generate/Set-on.
- Milestone 4 (spec §5): SQLite-backed library replacing `MOCK_LIBRARY`.
- Milestone 5 (spec §4): `IDesktopWallpaper` COM + real monitor enumeration replacing `MOCK_MONITORS`.
- Deleting `wallpaper.py`, once nothing references it and the CLI (if built) supersedes it.
