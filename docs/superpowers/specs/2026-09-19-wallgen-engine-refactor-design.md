# WallGen engine refactor — design

**Status:** approved, ready for implementation planning
**Relates to:** [docs/wallgen-spec.md](../../wallgen-spec.md) §3 (step one: turn the script into a library), §7 build-order Milestone 1

## Goal

Turn the root-level `wallpaper.py` (~810 lines, a standalone argparse script) into
`src/wallgen/engine/`: a pure library with no argparse, no module-level RNG, and no
import-time `sys.exit()`, matching the architecture already committed to in the spec
and already assumed by the (mock-data) UI shell.

Done when `uv run python -c "from wallgen.engine import render, RenderSpec; render(RenderSpec()).save('x.png')"`
works, for all four styles.

**Out of scope for this task:**
- The `wallgen render` / `wallgen list` CLI entry point (spec keeps it, but it's a
  separate small task layered on top of the engine once it exists).
- Wiring the engine into the UI (`RenderJob`, `QThreadPool`, replacing mock data in
  `.viewport` / `.style_panel`) — that's Milestone 2.
- Deleting `wallpaper.py`. It becomes dead code once the engine package exists, but
  removing it is a separate cleanup decision, not part of this refactor.

## File structure

```
src/wallgen/engine/
├─ __init__.py       public surface: render(), preview(), RenderSpec, EngineError
├─ spec.py           RenderSpec dataclass, SIZES, PALETTES
├─ ctx.py            Ctx: scale, quiet zone, per-instance rng, layers
├─ common.py         font resolution (lazy), mul(), finish(), down(), glow(),
│                    base_gradient()
└─ styles/
   ├─ __init__.py
   ├─ pcb.py          render_pcb
   ├─ coderain.py     render_coderain
   ├─ terminal.py     render_terminal, parse_session, DEFAULT_SESSION
   └─ codeblock.py    render_codeblock, DEFAULT_CODE
```

This is a direct, mechanical mapping of `wallpaper.py`'s existing section comments
(`# --- presets`, `# --- context`, `# --- finishing`, `# --- style: pcb`, etc.) onto
separate files — no new abstractions, no behavior changes beyond the five fixes
below.

## The five changes (spec §3, applied per-file)

**1. `RenderSpec` replaces the argparse namespace** (`spec.py`).

Exact fields, confirmed against the current argparse namespace in `wallpaper.py`'s
`main()`:

```python
@dataclass(frozen=True, slots=True)
class RenderSpec:
    style: Style = "pcb"
    width: int = 2560
    height: int = 1440
    palette: str = "cyber"
    seed: int = 0
    quiet_zone: QuietZone = "left"
    mark: str = ""; submark: str = ""; chip_label: str = ""
    user: str = "you@localhost"; title: str = ""; session_text: str = ""
    code_text: str = ""; caption: str = ""
    glyphs: Literal["mixed", "ascii"] = "mixed"
    gutter: bool = True; cursor: bool = True

    def at(self, w: int, h: int) -> "RenderSpec":
        return replace(self, width=w, height=h)
```

`Style = Literal["pcb", "coderain", "terminal", "codeblock"]`,
`QuietZone = Literal["left", "right", "top", "bottom", "none"]` (five values — the
current `Ctx.quiet()`/`quiet_mask()` implementations already handle all five, the
spec's inline sketch just abbreviated the type comment).

`SIZES` and `PALETTES` move here unchanged (`wallpaper.py` lines 23–72).

**2. Per-instance RNG on `Ctx`** (`ctx.py`).

`Ctx.__init__` currently does `random.seed(self.seed)` — a hidden global that
corrupts output when two renders run concurrently (the preview render racing the
full-size render, which is exactly what Milestone 2's threading model does).

Fix: `self.rng = random.Random(spec.seed)`. Every style module's ~60 `random.*`
call sites become `ctx.rng.*` in the mechanical move to `styles/`. `Ctx.__init__`
also switches from reading `a.W`/`a.H` to `spec.width`/`spec.height`, since the
argparse namespace `a` no longer exists.

`np.random.default_rng(seed)` inside `finish()` is already per-call and needs no
change.

**3. Lazy, non-fatal font resolution** (`common.py`).

Current code resolves `FONTS` at import time and calls `sys.exit()` if no
monospace font is found — fatal on import, which is a landmine for a GUI process.

Fix: a small `EngineError(Exception)` (defined in `common.py`, re-exported from
`__init__.py`), and font resolution wrapped in a cached function:

```python
@functools.lru_cache(maxsize=1)
def _resolve_fonts() -> dict[str, str | None]:
    fonts = {role: next((c for c in cands if os.path.exists(c)), None)
             for role, cands in FONT_CANDIDATES.items()}
    if not fonts["mono"]:
        raise EngineError("no monospace font found — install fonts-dejavu-core")
    fonts["mono_b"] = fonts["mono_b"] or fonts["mono"]
    fonts["sans_b"] = fonts["sans_b"] or fonts["mono_b"]
    return fonts
```

`font(key, size)` calls `_resolve_fonts()` instead of reading a module-level
`FONTS` dict built at import.

Also add Windows CJK candidates to `FONT_CANDIDATES["cjk"]`, since the current list
is Linux-only paths and `coderain` silently falls back to ASCII on Windows:

```python
"cjk": [..., "C:/Windows/Fonts/YuGothR.ttc",
             "C:/Windows/Fonts/meiryo.ttc",
             "C:/Windows/Fonts/msgothic.ttc"],
```

**4. Progress callback** (threaded through `render()` and each style module).

Added now even though nothing calls it yet (the UI's `RenderJob`/`QThreadPool`
wiring is Milestone 2) — the spec's scope for this milestone includes it, and
adding it later would mean re-touching every style file a second time.

Signature: `progress: Callable[[float, str], None] | None = None`, passed from
`render()`/`preview()` down into each `render_*(ctx, spec, progress)` call, invoked
at 3–4 points per style (matching spec §3.4's granularity guidance) — e.g. after
occupancy-grid routing, after the finishing pipeline starts, etc. When `progress`
is `None`, style modules skip the calls (a no-op default, `progress = progress or
(lambda f, n: None)`, resolved once in `render()` rather than checked at every call
site).

**5. `preview()`** (`__init__.py`).

```python
def preview(spec: RenderSpec, max_width: int = 1280, progress=None) -> Image.Image:
    scale = min(1.0, max_width / spec.width)
    return render(spec.at(round(spec.width * scale), round(spec.height * scale)),
                  progress=progress)
```

## Public surface (`engine/__init__.py`)

```python
from wallgen.engine.spec import RenderSpec, SIZES, PALETTES
from wallgen.engine.common import EngineError

def render(spec: RenderSpec, progress=None) -> Image.Image: ...
def preview(spec: RenderSpec, max_width: int = 1280, progress=None) -> Image.Image: ...
```

`render()` dispatches on `spec.style` to the matching `styles/*.render_*` function
— the current `STYLES = {"pcb": render_pcb, ...}` dict moves here from the CLI
section, since it's now the engine's own dispatch table rather than an
argparse-choices helper.

## Default session/code text

`wallpaper.py`'s `main()` currently substitutes `DEFAULT_SESSION`/`DEFAULT_CODE`
when the `--script`/`--code` CLI flags are omitted. `RenderSpec` defaults
`session_text`/`code_text` to `""` (per spec §3.1's dataclass), and there is no CLI
in this task to do the substitution. So that fallback moves into the style
functions themselves:

```python
# styles/terminal.py
def render_terminal(ctx, spec):
    text = spec.session_text or DEFAULT_SESSION
    rows = parse_session(text)
    ...
```

Same pattern in `codeblock.py` for `code_text`/`DEFAULT_CODE`. This keeps
`render(RenderSpec(style="terminal"))` producing a sensible image out of the box,
which matters for the determinism test and for milestone 1's done-criteria example.

## Testing

`tests/engine/test_determinism.py`:

```python
def test_render_is_deterministic_under_concurrency():
    spec = RenderSpec(style="pcb", width=640, height=360, seed=7)
    once = render(spec).tobytes()
    with ThreadPoolExecutor(4) as ex:
        results = [f.result().tobytes() for f in
                   [ex.submit(render, spec) for _ in range(4)]]
    assert all(r == once for r in results)
```

This is the one correctness risk that can silently corrupt output rather than
crash (spec §3.2, §9.1) — the change this task exists to make. It's the only test
that matters for verifying the RNG fix actually works.

`tests/engine/test_render_smoke.py`: for each of the four styles, `render()` and
`preview()` return a `PIL.Image` of the expected size. No per-style unit tests
beyond that (not testing pixel content, layout correctness, or CLI behavior — none
of that changed).

## Non-goals / explicitly deferred

- CLI (`wallgen render`, `wallgen list`) — separate task.
- Deleting `wallpaper.py` — separate cleanup decision.
- Wiring `render()`/`preview()` into the UI's `RenderJob` — Milestone 2.
- Any change to render output/visual behavior — this is a structural refactor only;
  pixel output for a given `(style, seed, size, palette, ...)` should be unchanged
  except where the RNG fix changes call-site ordering in a way that was already
  nondeterministic under concurrency (i.e., single-threaded output is unaffected).
