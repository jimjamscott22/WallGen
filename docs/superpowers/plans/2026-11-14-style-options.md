# Style Options and Blueprint Subjects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the user a built-in menu of Blueprint subjects plus on/off and amount options inside the Blueprint, PCB, Contour and Code rain styles, in the GUI panel and on `wallgen render`.

**Architecture:** Twelve flat, defaulted fields are added to `RenderSpec`; each style function checks its fields while drawing. Blueprint is split into a sheet (`blueprint.py`) and a registry of subject functions (`blueprint_subjects.py`). The options panel and the CLI gain one entry per field; no new widget kinds, no saved-format change.

**Tech Stack:** Python 3.12, Pillow, numpy, PySide6, pytest / pytest-qt, `uv`.

**Spec:** `docs/superpowers/specs/2026-11-14-style-options-design.md` — read it before starting; this plan argues from it.

## Global Constraints

- With every new field at its default, each style consumes `ctx.rng` in the same order as today and renders the **same bytes** as before this change. Every engine task ends with the baseline comparison from Task 1.
- New `RenderSpec` fields are flat, `str` or `bool`, and defaulted, so `RenderSpec(**json.loads(spec_json))` still loads old rows.
- `engine/` has no Qt, no win32, no disk writes. `cli.py` imports no Qt.
- All drawing constants are in units (`ctx.u`, `ctx.s`, or the Blueprint `unit`); no hard-coded pixels. Only seeded randomness (`ctx.rng`). Honor `spec.quiet_zone` as each style does today.
- Terminal and Code block are not touched. No new styles or palettes.
- Contour line counts are fixed at 19 / 31 / 43. PCB and Code rain density factors below are starting values the implementer may tune by eye; tests only require the ordering.
- Run tests with `uv run pytest`; run `uv sync` once first. Commits follow Conventional Commits and end with the session's attribution lines.

## Review Focus

Conditions the spec implies that a user will hit; each has a test in the task named.

1. A library entry saved before this change (no new keys in `spec_json`) loads and equals the default-option spec — Task 1.
2. Every subject at portrait, ultrawide and tiny sizes, in both layouts and with every quiet zone, renders without error (tiny sizes skip lettering; line widths never reach 0) — Task 3.
3. PCB with the hero chip off while `chip_label` and `mark` are set: renders, the wordmark is still drawn, nothing crashes on the missing chip — Task 4.
4. Everything switched off at once (PCB: no chips, sparse, no components; Blueprint: no grid, dimensions or labels) still renders a non-blank design — Tasks 2 and 4.
5. Loading a library entry with non-default options restores every new editor, including those on hidden pages — Task 7.

## File Map

| File | Responsibility |
|---|---|
| `src/wallgen/engine/spec.py` | the twelve fields and four `Literal` aliases |
| `src/wallgen/engine/styles/blueprint.py` | sheet: grid, focus point, calls the subject, title block |
| `src/wallgen/engine/styles/blueprint_subjects.py` (new) | `Pen`, the four subject functions, `SUBJECTS` |
| `src/wallgen/engine/styles/pcb.py`, `contour.py`, `coderain.py` | gate their parts |
| `src/wallgen/ui/style_options.py` | new `Field` rows |
| `src/wallgen/cli.py` | flags, `list` section, default filename |
| `tests/engine/test_defaults_frozen.py` (new) | permanent coarse fingerprint of today's defaults |
| `tests/engine/test_style_options.py` (new) | engine behaviour of every option |

---

### Task 1: Spec fields and the frozen baseline

**Files:**
- Modify: `src/wallgen/engine/spec.py`
- Create: `tests/engine/test_defaults_frozen.py`, `.baseline/check.py` (untracked)
- Test: `tests/engine/test_spec.py`, `tests/test_library_store.py`

**Interfaces:**
- Produces, in `wallgen.engine.spec`:
  - `BlueprintSubject = Literal["flange", "gear", "bearing", "bracket"]`
  - `TraceDensity = Literal["sparse", "normal", "dense"]`
  - `ContourLines = Literal["few", "normal", "many"]`
  - `RainDensity = Literal["light", "normal", "heavy"]`
  - `RenderSpec` fields, appended after `contour_layout`: `blueprint_subject: BlueprintSubject = "flange"`, `blueprint_grid: bool = True`, `blueprint_dimensions: bool = True`, `blueprint_labels: bool = True`, `pcb_hero_chip: bool = True`, `pcb_small_chips: bool = True`, `pcb_traces: TraceDensity = "normal"`, `pcb_components: bool = True`, `contour_lines: ContourLines = "normal"`, `contour_accent: bool = True`, `rain_density: RainDensity = "normal"`, `rain_foreground: bool = True`
  - `uv run python .baseline/check.py compare` — exits 0 when current renders match the saved pre-change bytes.

- [ ] **Step 1: Save the byte baseline from the unchanged code**

Add `.baseline/` to `.git/info/exclude`, then create `.baseline/check.py`:

```python
"""save | compare: sha256 of default-option renders, to prove defaults are frozen."""
import hashlib, itertools, json, sys
from pathlib import Path
from wallgen.engine import RenderSpec, render

CASES = [dict(style="pcb"), dict(style="pcb", mark="WALLGEN", submark="SUB", chip_label="WG-1"),
         dict(style="coderain"), dict(style="coderain", glyphs="ascii"),
         dict(style="blueprint"), dict(style="blueprint", blueprint_layout="offset"),
         dict(style="contour"), dict(style="contour", contour_layout="island")]
SIZES = [(960, 540), (540, 960), (320, 180)]
FILE = Path(__file__).with_name("hashes.json")

def hashes():
    out = {}
    for case, (w, h), seed, zone in itertools.product(CASES, SIZES, (7, 20260813), ("left", "top", "none")):
        spec = RenderSpec(width=w, height=h, seed=seed, quiet_zone=zone, **case)
        out[json.dumps([case, w, h, seed, zone])] = hashlib.sha256(render(spec).tobytes()).hexdigest()
    return out

if sys.argv[1] == "save":
    FILE.write_text(json.dumps(hashes()))
else:
    bad = [k for k, v in hashes().items() if json.loads(FILE.read_text())[k] != v]
    print("\n".join(bad) or "baseline OK")
    sys.exit(1 if bad else 0)
```

Run: `uv run python .baseline/check.py save && uv run python .baseline/check.py compare`
Expected: `baseline OK`

- [ ] **Step 2: Write the permanent fingerprint test from the unchanged code**

`tests/engine/test_defaults_frozen.py`. Only font-free cases, and a coarse fingerprint with tolerance so it holds across platforms:

```python
CASES = {  # name -> spec kwargs; none of these draw text
    "pcb": dict(style="pcb", width=640, height=360, seed=7),
    "contour-ridge": dict(style="contour", width=640, height=360, seed=7),
    "contour-island": dict(style="contour", width=640, height=360, seed=7, contour_layout="island"),
    "blueprint": dict(style="blueprint", width=320, height=180, seed=7),  # too small for lettering
}
EXPECTED = {...}  # name -> list of 32*18 ints

def fingerprint(image):
    return list(image.convert("L").resize((32, 18), Image.BOX).getdata())

@pytest.mark.parametrize("name", CASES)
def test_default_options_render_what_they_did_before_style_options(name):
    actual = fingerprint(render(RenderSpec(**CASES[name])))
    assert max(abs(a - e) for a, e in zip(actual, EXPECTED[name])) <= 2
```

Fill `EXPECTED` by printing `fingerprint(...)` for each case from the current code.

Run: `uv run pytest tests/engine/test_defaults_frozen.py -v` — Expected: 4 passed.

- [ ] **Step 3: Write the failing spec tests**

In `tests/engine/test_spec.py`:

```python
def test_style_option_defaults_keep_todays_look():
    spec = RenderSpec()
    assert spec.blueprint_subject == "flange"
    assert spec.pcb_traces == spec.contour_lines == spec.rain_density == "normal"
    assert all(getattr(spec, name) is True for name in (
        "blueprint_grid", "blueprint_dimensions", "blueprint_labels", "pcb_hero_chip",
        "pcb_small_chips", "pcb_components", "contour_accent", "rain_foreground"))
```

In `tests/test_library_store.py`, next to `test_legacy_library_spec_uses_layout_defaults` and in the same shape:

```python
def test_library_spec_saved_before_style_options_still_loads(store):
    # delete all twelve new keys from the stored spec_json, then:
    assert LibraryStore(store.root).get(path.stem).spec == spec
```

Run: `uv run pytest tests/engine/test_spec.py tests/test_library_store.py -v` — Expected: both new tests FAIL (unknown attribute / `KeyError`).

- [ ] **Step 4: Add the aliases and fields to `spec.py`** exactly as listed under Interfaces.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest` — Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/wallgen/engine/spec.py tests/engine/test_spec.py tests/engine/test_defaults_frozen.py tests/test_library_store.py
git commit -m "feat: add style option fields to RenderSpec"
```

---

### Task 2: Blueprint sheet, subject registry and switches

After this task `blueprint_subject` values other than `"flange"` raise `KeyError`; Task 3 adds them. Nothing exposes them to the user yet.

**Files:**
- Create: `src/wallgen/engine/styles/blueprint_subjects.py`, `tests/engine/test_style_options.py`
- Modify: `src/wallgen/engine/styles/blueprint.py`

**Interfaces:**
- Consumes: `RenderSpec.blueprint_subject / blueprint_grid / blueprint_dimensions / blueprint_labels`.
- Produces, in `blueprint_subjects.py`:

```python
class Pen:
    """Draws in subject units around the sheet's focus point."""
    fine: tuple; main: tuple; accent: tuple      # mul(primary,.36), mul(primary,.86), mul(accent,.78)
    lettering: bool                              # False when 25 * unit / ctx.S < 5
    def __init__(self, draw, cx: float, cy: float, unit: float, palette: dict, lettering: bool): ...
    def point(self, x, y) -> tuple[float, float]: ...
    def line(self, points, color, weight=2) -> None: ...        # open polyline
    def circle(self, x, y, radius, color, weight=2) -> None: ...
    def outline(self, points, color, weight=2) -> None: ...     # closed polyline
    def text(self, x, y, text, color, *, size=25, bold=False, anchor="ms") -> None: ...  # no-op unless lettering
    def title_block(self, title: str, caption: str) -> None: ...

SubjectFn = Callable[[Pen, random.Random, bool], None]   # (pen, rng, dimensions)
SUBJECTS: dict[str, tuple[SubjectFn, str]]                # name -> (draw function, title)
# this task registers: "flange": (draw_flange, "FLANGE ASSEMBLY")
```

`title_block` draws what the flange draws today under the subject: the fine rule from `(-479, 362)` to `(479, 362)`, the title at `(-479, 387)` bold size 35 anchor `"lt"` in `main`, the caption at `(479, 387)` size 25 anchor `"rt"` in `fine`.

- [ ] **Step 1: Write the failing tests** in `tests/engine/test_style_options.py`

```python
def image(**kwargs):
    kwargs = {"width": 960, "height": 540, "seed": 7, **kwargs}   # large enough for lettering
    return np.asarray(render(RenderSpec(**kwargs)), np.int16)

@pytest.mark.parametrize("switch", ["blueprint_grid", "blueprint_dimensions", "blueprint_labels"])
def test_each_blueprint_switch_changes_the_image(switch):
    assert (image(style="blueprint") != image(style="blueprint", **{switch: False})).any()

def test_blueprint_with_every_switch_off_still_draws_the_subject():
    bare = dict(style="blueprint", blueprint_grid=False, blueprint_dimensions=False, blueprint_labels=False)
    assert (image(**bare) != image(**bare, seed=8)).any()       # seeded geometry is there
    assert image(**bare).max() > 120                             # main-weight linework is visible

def test_flange_is_registered_with_its_title():
    assert SUBJECTS["flange"][1] == "FLANGE ASSEMBLY"
```

Run: `uv run pytest tests/engine/test_style_options.py -v` — Expected: FAIL (import error for `SUBJECTS`).

- [ ] **Step 2: Create `blueprint_subjects.py`** with `Pen`, `draw_flange(pen, rng, dimensions)` and `SUBJECTS`.

Move the flange code out of `render_blueprint` unchanged in draw order and in the order of its four `rng` calls (`randint(252, 286)`, `randint(83, 115)`, `choice((6, 8, 10))`, `uniform(0, tau / holes)`). Centre dashes, rings and bolt holes are always drawn. The extension lines, tick marks, dimension line, both leaders and the three measurement texts are drawn only when `dimensions`.

- [ ] **Step 3: Reduce `render_blueprint` to the sheet**

Grid only when `spec.blueprint_grid`. Build the `Pen` (the `offset` layout's focus point and `unit *= 0.72` stay here). Then `draw, title = SUBJECTS[spec.blueprint_subject]`, `draw(pen, ctx.rng, spec.blueprint_dimensions)`, and `pen.title_block(title, "FRONT VIEW / A")` when `spec.blueprint_labels`. Progress stays at 0.25 / 0.65 / 0.88; the 0.65 note becomes `f"drawing {title.lower()}"`.

- [ ] **Step 4: Verify**

Run: `uv run pytest tests/engine -v && uv run python .baseline/check.py compare`
Expected: all pass, `baseline OK`.

- [ ] **Step 5: Commit** — `git commit -m "feat: split Blueprint into a sheet and switchable subject parts"`

---

### Task 3: Gear, bearing and bracket subjects

**Files:**
- Modify: `src/wallgen/engine/styles/blueprint_subjects.py`
- Test: `tests/engine/test_style_options.py`

**Interfaces:**
- Consumes: `Pen`, `SubjectFn`, `SUBJECTS` from Task 2.
- Produces: `SUBJECTS` entries `"gear": (draw_gear, "SPUR GEAR")`, `"bearing": (draw_bearing, "BALL BEARING")`, `"bracket": (draw_bracket, "MOUNTING BRACKET")`.

- [ ] **Step 1: Write the failing tests**

```python
SUBJECT_NAMES = get_args(BlueprintSubject)

def test_registry_matches_the_spec_choices():
    assert tuple(SUBJECTS) == SUBJECT_NAMES

def test_subjects_are_distinct_and_seeded():
    images = {name: image(style="blueprint", blueprint_subject=name) for name in SUBJECT_NAMES}
    for a, b in itertools.combinations(SUBJECT_NAMES, 2):
        assert (images[a] != images[b]).any()
    for name in SUBJECT_NAMES:
        assert (images[name] != image(style="blueprint", blueprint_subject=name, seed=8)).any()

@pytest.mark.parametrize("subject", SUBJECT_NAMES)
@pytest.mark.parametrize("size", [(295, 640), (860, 360), (96, 54)])      # portrait, ultrawide, tiny
@pytest.mark.parametrize("layout", ["centered", "offset"])
def test_subjects_render_at_awkward_sizes(subject, size, layout):
    for zone in get_args(QuietZone):
        spec = RenderSpec(style="blueprint", width=size[0], height=size[1], seed=3, quiet_zone=zone,
                          blueprint_subject=subject, blueprint_layout=layout)
        assert render(spec).size == size

@pytest.mark.parametrize("subject", SUBJECT_NAMES)
def test_subject_dimensions_switch_changes_the_image(subject):
    on = image(style="blueprint", blueprint_subject=subject)
    assert (on != image(style="blueprint", blueprint_subject=subject, blueprint_dimensions=False)).any()
```

Run: `uv run pytest tests/engine/test_style_options.py -v` — Expected: new tests FAIL with `KeyError: 'gear'`.

- [ ] **Step 2: Implement the three subject functions**

Each is an orthographic front view using `pen.main` for outlines (weights 3–4), `pen.fine` for centre lines and construction circles, and `pen.accent` for dimensions, inside the flange's envelope: x within ±480, y from −390 to 340 (the title block owns everything below). Each draws dashed centre lines like the flange, and draws its dimension lines, leaders and three callout texts only when `dimensions`. Geometry and exact ranges are the implementer's, within:

| Subject | Seeded by `rng` | Geometry | Callouts |
|---|---|---|---|
| gear | teeth 14–24, bore radius, lightening holes 0 / 4 / 5 / 6 | trapezoidal-tooth outline (`pen.outline`), dashed pitch circle, hub ring, bore with a rectangular keyway | `OD … mm`, `BORE … mm`, `{n} TEETH` |
| bearing | balls 8–12, race proportions | outer race (two circles), inner race (two circles), ring of balls, cage circle, bore | `OD … mm`, `BORE … mm`, `{n}x BALLS` |
| bracket | plate width and height, holes 4 or 6, slot length | rounded-rectangle plate, mounting holes near the corners (and mid-edges when 6), central slot with rounded ends | `W … mm`, `H … mm`, `{n}x MOUNT HOLES` |

Millimetre values use the flange's convention, units ÷ 5 with one decimal.

- [ ] **Step 3: Look at them**

Run: `for s in gear bearing bracket; do uv run python -c "from wallgen.engine import RenderSpec, render; render(RenderSpec(style='blueprint', blueprint_subject='$s', width=1920, height=1080, seed=7)).save('.baseline/$s.png')"; done`

Open each PNG and compare with a flange render: lines must not collide with the callouts or the title block, and each must look as finished as the flange. Repeat with `blueprint_layout='offset'` and one portrait size. Adjust until they do.

- [ ] **Step 4: Verify**

Run: `uv run pytest tests/engine -v && uv run python .baseline/check.py compare` — Expected: all pass, `baseline OK`.

- [ ] **Step 5: Commit** — `git commit -m "feat: add gear, bearing and bracket Blueprint subjects"`

---

### Task 4: PCB options

**Files:**
- Modify: `src/wallgen/engine/styles/pcb.py`
- Test: `tests/engine/test_style_options.py`

**Interfaces:**
- Consumes: `RenderSpec.pcb_hero_chip / pcb_small_chips / pcb_traces / pcb_components`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("option", [dict(pcb_hero_chip=False), dict(pcb_small_chips=False),
                                    dict(pcb_traces="sparse"), dict(pcb_traces="dense"),
                                    dict(pcb_components=False)])
def test_each_pcb_option_changes_the_image(option):
    assert (image(style="pcb") != image(style="pcb", **option)).any()

def test_trace_density_orders_the_amount_of_light():
    sparse, normal, dense = (image(style="pcb", pcb_traces=v).mean() for v in ("sparse", "normal", "dense"))
    assert sparse < normal < dense

def test_removing_components_leaves_the_traces_in_place():
    default, off = image(style="pcb"), image(style="pcb", pcb_components=False)
    assert (off - default).max() <= 24      # nothing new appears: no trace moved
    assert (default - off).max() >= 40      # something bright was removed

def test_hero_chip_off_ignores_its_label_and_keeps_the_wordmark():
    marked = dict(style="pcb", pcb_hero_chip=False, mark="WALLGEN", chip_label="WG-1")
    assert (image(**marked) == image(**{**marked, "chip_label": ""})).all()
    assert (image(**marked) != image(**{**marked, "mark": ""})).any()

def test_pcb_with_everything_off_is_not_blank():
    bare = image(style="pcb", pcb_hero_chip=False, pcb_small_chips=False,
                 pcb_traces="sparse", pcb_components=False)
    assert bare.max() > 120
```

Run: `uv run pytest tests/engine/test_style_options.py -k pcb -v` — Expected: FAIL (options have no effect).

- [ ] **Step 2: Gate the parts in `render_pcb`**

- `pcb_hero_chip` off: skip the hero `chip(...)` call and the fan-out loop that follows "routing traces". `hx`, `hy`, `HCX`, `HCY` and `hero` are still computed (the background gradient uses the focus).
- `pcb_small_chips` off: skip the loop over the four secondary chips.
- `pcb_traces`: factor `{"sparse": 0.5, "normal": 1.0, "dense": 1.6}`, multiplied into both `n` and `tries` of the three `scatter(...)` calls, inside the existing `int(...)`.
- `pcb_components` off: skip both loops between "routing traces" and "adding silkscreen" that call `free_spot` (pads and dots). Still report that progress step.

- [ ] **Step 3: Verify**

Run: `uv run pytest tests/engine -v && uv run python .baseline/check.py compare` — Expected: all pass, `baseline OK`.
If `test_removing_components_leaves_the_traces_in_place` fails only on the first bound by a few counts, that is resampling ringing next to a trace, not a moved trace: raise the bound, to at most 40.

- [ ] **Step 4: Commit** — `git commit -m "feat: add PCB chip, trace density and component options"`

---

### Task 5: Contour options

**Files:**
- Modify: `src/wallgen/engine/styles/contour.py`
- Test: `tests/engine/test_style_options.py`

**Interfaces:**
- Consumes: `RenderSpec.contour_lines / contour_accent`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("layout", ["ridge", "island"])
@pytest.mark.parametrize("option", [dict(contour_lines="few"), dict(contour_lines="many"),
                                    dict(contour_accent=False)])
def test_each_contour_option_changes_the_image(layout, option):
    base = dict(style="contour", contour_layout=layout)
    assert (image(**base) != image(**base, **option)).any()

@pytest.mark.parametrize("layout", ["ridge", "island"])
def test_line_count_orders_the_amount_of_light(layout):
    few, normal, many = (image(style="contour", contour_layout=layout, contour_lines=v).mean()
                         for v in ("few", "normal", "many"))
    assert few < normal < many
```

Run: `uv run pytest tests/engine/test_style_options.py -k contour -v` — Expected: FAIL.

- [ ] **Step 2: Generalise the line loop in `render_contour`**

With `k = {"few": 3, "normal": 5, "many": 7}[spec.contour_lines]` the loop runs over `range(6 * k + 1)` (19 / 31 / 43 lines):

- ridge: `level = (index - 3 * k) / (3 * k)`; prominence unchanged in terms of `level`.
- island: level `0.08 + 0.92 * index / (6 * k)`; `prominence = 1 - (index * 5 / k) / 42`.
- major line: `index % k == 0`.
- accent line: `index == (k if island else 3 * k)`, and only when `spec.contour_accent`; otherwise primary.

These forms reduce to today's exact arithmetic at `k = 5`. The four `ctx.rng` calls above the loop are untouched.

- [ ] **Step 3: Verify**

Run: `uv run pytest tests/engine -v && uv run python .baseline/check.py compare` — Expected: all pass, `baseline OK`.

- [ ] **Step 4: Commit** — `git commit -m "feat: add Contour line count and accent options"`

---

### Task 6: Code rain options

**Files:**
- Modify: `src/wallgen/engine/styles/coderain.py`
- Test: `tests/engine/test_style_options.py`

**Interfaces:**
- Consumes: `RenderSpec.rain_density / rain_foreground`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("option", [dict(rain_density="light"), dict(rain_density="heavy"),
                                    dict(rain_foreground=False)])
def test_each_rain_option_changes_the_image(option):
    assert (image(style="coderain") != image(style="coderain", **option)).any()

def test_rain_density_orders_the_amount_of_light():
    light, normal, heavy = (image(style="coderain", rain_density=v).mean()
                            for v in ("light", "normal", "heavy"))
    assert light < normal < heavy

def test_removing_foreground_streaks_leaves_the_rest_in_place():
    default, off = image(style="coderain"), image(style="coderain", rain_foreground=False)
    assert (off - default).max() <= 1
    assert (default - off).max() >= 10
```

Run: `uv run pytest tests/engine/test_style_options.py -k rain -v` — Expected: FAIL.

- [ ] **Step 2: Gate the planes in `render_coderain`**

- `rain_density`: factor `{"light": 0.55, "normal": 1.0, "heavy": 1.5}` multiplied into the `columns` argument of all four `plane(...)` calls, inside the existing `int(...)`.
- `rain_foreground` off: do not build the `near` plane (it is the last consumer of `ctx.rng`) and skip the two lines that add it to `out`.

- [ ] **Step 3: Verify**

Run: `uv run pytest tests/engine -v && uv run python .baseline/check.py compare` — Expected: all pass, `baseline OK`.

- [ ] **Step 4: Commit** — `git commit -m "feat: add Code rain density and foreground options"`

---

### Task 7: Options panel

**Files:**
- Modify: `src/wallgen/ui/style_options.py`
- Test: `tests/ui/test_style_options.py`, `tests/ui/test_main_window.py`

**Interfaces:**
- Consumes: the `Literal` aliases and field names from Task 1.

- [ ] **Step 1: Write the failing tests**

In `tests/ui/test_style_options.py`, add the twelve field names to `SPEC_KEYS`, and add:

```python
def test_style_option_editors_and_their_choices(qtbot):
    panel = StyleOptionsPanel()
    qtbot.addWidget(panel)
    def items(key):
        combo = panel.editor(key)
        return [combo.itemText(i) for i in range(combo.count())], combo.currentText()
    assert items("blueprint_subject") == (["flange", "gear", "bearing", "bracket"], "flange")
    assert items("pcb_traces") == (["sparse", "normal", "dense"], "normal")
    assert items("contour_lines") == (["few", "normal", "many"], "normal")
    assert items("rain_density") == (["light", "normal", "heavy"], "normal")
    for key in ("blueprint_grid", "blueprint_dimensions", "blueprint_labels", "pcb_hero_chip",
                "pcb_small_chips", "pcb_components", "contour_accent", "rain_foreground"):
        assert isinstance(panel.editor(key), QCheckBox) and panel.editor(key).isChecked()

def test_loading_a_spec_restores_style_options_on_every_page(qtbot):
    panel = StyleOptionsPanel()
    qtbot.addWidget(panel)
    spec = RenderSpec(style="contour", blueprint_subject="gear", blueprint_grid=False,
                      pcb_traces="dense", pcb_hero_chip=False, contour_lines="few",
                      contour_accent=False, rain_density="heavy", rain_foreground=False)
    panel.load_spec(spec)
    assert RenderSpec(style="contour", **panel.values()) == spec
```

In `tests/ui/test_main_window.py`, building the window the way that file's other tests do:

```python
def test_the_tallest_options_page_fits_the_default_window(qtbot, ...):
    window.resize(1440, 900)
    window.style_panel.set_style("pcb")
    assert window.minimumSizeHint().height() <= 900
```

Run: `uv run pytest tests/ui/test_style_options.py tests/ui/test_main_window.py -v` — Expected: the new tests and `test_values_cover_every_spec_field...` FAIL.

- [ ] **Step 2: Add the `Field` rows to `FIELDS_BY_STYLE`**

Choices come from `get_args` of the alias, defaults from `_DEFAULTS`. Order and labels:

| Style | Rows appended, in order (label → key) |
|---|---|
| pcb | Traces → `pcb_traces`; Hero chip → `pcb_hero_chip`; Small chips → `pcb_small_chips`; Components → `pcb_components` |
| coderain | Density → `rain_density`; Foreground streaks → `rain_foreground` |
| blueprint | Subject → `blueprint_subject` (placed **before** Layout); Grid → `blueprint_grid`; Dimensions → `blueprint_dimensions`; Labels → `blueprint_labels` |
| contour | Lines → `contour_lines`; Accent line → `contour_accent` |

- [ ] **Step 3: Verify**

Run: `uv run pytest tests/ui -v` — Expected: all pass. If the fit test fails, reduce the PCB page's spacing rather than making the panel scroll.

- [ ] **Step 4: Commit** — `git commit -m "feat: show style options in the options panel"`

---

### Task 8: Command line and docs

**Files:**
- Modify: `src/wallgen/cli.py`, `README.md`, `CLAUDE.md`, `docs/wallgen-spec.md`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: field names and aliases from Task 1; `SUBJECTS` is **not** imported here — use `get_args(BlueprintSubject)`.

- [ ] **Step 1: Write the failing tests** in `tests/test_cli.py`

```python
def test_every_style_option_flag_reaches_the_spec():
    args = cli.build_parser().parse_args([
        "render", "--seed", "1", "--blueprint-subject", "gear", "--no-blueprint-grid",
        "--no-blueprint-dimensions", "--no-blueprint-labels", "--no-hero-chip", "--no-small-chips",
        "--traces", "dense", "--no-components", "--contour-lines", "few", "--no-contour-accent",
        "--rain-density", "heavy", "--no-rain-foreground"])
    assert cli.spec_from_args(args) == RenderSpec(
        seed=1, blueprint_subject="gear", blueprint_grid=False, blueprint_dimensions=False,
        blueprint_labels=False, pcb_hero_chip=False, pcb_small_chips=False, pcb_traces="dense",
        pcb_components=False, contour_lines="few", contour_accent=False,
        rain_density="heavy", rain_foreground=False)

def test_a_non_default_subject_is_in_the_default_filename(capsys, here):
    args = ("render", "--style", "blueprint", "--size", "320x180", "--seed", "7")
    assert run(capsys, *args, "--blueprint-subject", "gear")[0] == 0
    assert (here / "wallpaper-blueprint-gear-centered-320x180-7.png").is_file()

def test_list_prints_the_blueprint_subjects(capsys):
    _, out, _ = run(capsys, "list")
    assert out.split("BLUEPRINT SUBJECTS\n", 1)[1].split() == list(get_args(BlueprintSubject))
```

Change `test_list_prints_every_size_palette_and_style` so the styles assertion reads only the STYLES block: `out.split("STYLES\n", 1)[1].split("\n\n", 1)[0].split()`.

Run: `uv run pytest tests/test_cli.py -v` — Expected: the three new tests FAIL.

- [ ] **Step 2: Implement in `cli.py`**

- Flags go in the existing per-style argument groups, with `dest` equal to the spec field name, defaults from `RenderSpec()`, `--no-…` flags as `store_false`, choice flags with `choices=get_args(alias)`. Flag names are exactly those in the test above.
- `spec_from_args` passes all twelve.
- Default filename: for Blueprint, `blueprint-{subject}-{layout}` when the subject is not `flange`; unchanged otherwise.
- `_list()` prints a `BLUEPRINT SUBJECTS` section after `STYLES`, in the same format.

- [ ] **Step 3: Update the docs**

- `README.md`: one CLI example using `--blueprint-subject gear` and one `--no-…` flag, next to the existing examples; mention the Subject menu where the styles are described.
- `CLAUDE.md`, architecture bullet for `engine/`: Blueprint subjects live in `engine/styles/blueprint_subjects.py`; adding one means a draw function, a `SUBJECTS` entry and a `BlueprintSubject` literal value.
- `docs/wallgen-spec.md`, under "Out, on purpose": keep the style-editor line and add that per-style options and built-in Blueprint subjects are in scope, pointing at the design doc.

- [ ] **Step 4: Verify everything**

Run: `uv run pytest && uv run python .baseline/check.py compare`
Expected: all pass, `baseline OK`.
Run: `uv run wallgen render --style blueprint --blueprint-subject bearing --no-blueprint-grid --size 1280x720 --seed 7 --out .baseline/cli.png`
Expected: one line ending `style=blueprint palette=cyber seed=7`, and the PNG shows a bearing with no grid.

- [ ] **Step 5: Commit and push** — `git commit -m "feat: add style option flags to wallgen render"`, then push the branch. If the Windows CI run fails only in `tests/engine/test_defaults_frozen.py`, the fingerprints are not portable: delete that file, say so in the PR, and rely on the local baseline.
