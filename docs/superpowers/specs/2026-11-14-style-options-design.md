# Style options and Blueprint subjects — design

Date: 2026-11-14
Status: awaiting approval

## Intent

WallGen decides the design; the user only picks a style, palette, seed and a
few text fields. The owner wants more say over what goes into a wallpaper,
"like the way Canva lets the user pick objects from a menu", but without
rewriting more of the app than necessary. Free placement of single objects was
considered and set aside by the owner: a single object does not make a full
wallpaper, and "additional options" are the right first step.

So this change adds choices inside four existing styles:

- a built-in collection of Blueprint subjects to pick from, and
- on/off switches and amount settings for parts the styles already draw.

## Goals

1. Blueprint has a **Subject** menu with four built-in subjects: flange (the
   existing one), gear, bearing, bracket.
2. Blueprint, PCB, Contour and Code rain each gain the options in the table
   below, in the right-hand options panel and on `wallgen render`.
3. Every new option defaults to today's look. A spec with all defaults renders
   the same image as before this change, and every `spec_json` row already in a
   library still loads and re-renders as the same design.
4. Options are saved with the wallpaper like any other setting, so loading a
   library entry restores them.

## Non-goals

- Free placement, dragging, or any interaction with the preview.
- Mixing parts across styles (contour background + blueprint subject, etc.).
- New styles, new palettes, or changes to Terminal and Code block.
- User-supplied artwork or imported shapes.

## Anti-goals

- Changing what an existing seed produces at default settings.
- A general "parts" framework or a rewrite of the style functions beyond what
  the options need.
- Breaking the engine rules in `CLAUDE.md`: no Qt in `engine/`, all constants in
  units, seeded randomness only, quiet zone honored.

## The options

Decided with the owner (the list and the four subjects are approved):

| Style | Option | Kind | Values (default first) | Spec field |
|---|---|---|---|---|
| Blueprint | Subject | choice | flange, gear, bearing, bracket | `blueprint_subject` |
| Blueprint | Grid | check | on | `blueprint_grid` |
| Blueprint | Dimensions | check | on | `blueprint_dimensions` |
| Blueprint | Labels | check | on | `blueprint_labels` |
| PCB | Hero chip | check | on | `pcb_hero_chip` |
| PCB | Small chips | check | on | `pcb_small_chips` |
| PCB | Traces | choice | normal, sparse, dense | `pcb_traces` |
| PCB | Components | check | on | `pcb_components` |
| Contour | Lines | choice | normal, few, many | `contour_lines` |
| Contour | Accent line | check | on | `contour_accent` |
| Code rain | Density | choice | normal, light, heavy | `rain_density` |
| Code rain | Foreground streaks | check | on | `rain_foreground` |

Existing options (Blueprint/Contour layout, PCB wordmark fields, Code rain
glyphs) stay as they are. In the UI, choice lists are shown in a natural order
(sparse / normal / dense) with the default preselected.

What each one means (author's calls, grounded in the current code):

**Blueprint**
- *Grid*: the drafting grid behind the subject.
- *Dimensions*: the accent-coloured dimension lines, leaders and tick marks,
  together with their measurement text ("OD 108.0 mm", "8x BOLT HOLES"…).
- *Labels*: the title line and view caption under the subject
  ("FLANGE ASSEMBLY", "FRONT VIEW / A") and the rule above them.
- The subject's own centre lines and geometry are always drawn.
- The existing rule that tiny renders skip all lettering stays.

**PCB**
- *Hero chip*: the large chip. When off, its label is not drawn, its space is
  not reserved, and the fan-out traces that start at its edge are skipped, so
  ordinary traces route through the area. (A chip-shaped hole would look
  broken.) The background glow keeps its position.
- *Small chips*: the four secondary chips; when off, traces fill their space.
- *Traces*: scales the count of the three scattered trace tiers. Suggested
  factors 0.5 / 1 / 1.6; the builder tunes them by eye.
- *Components*: the small outlined pads and the bright dots drawn after the
  traces (the stage reported as "adding silkscreen").

**Contour**
- *Lines*: number of contour lines, 31 today. Counts are 19 / 31 / 43 (author's
  call, fixed, not tunable): each has the form 6k+1, so the terrain keeps the
  same shape and only the spacing between lines changes. Major lines stay at
  every sixth of the span (every 3rd, 5th or 7th line), and the accent line
  stays where it is today: the centre line in the ridge layout, one sixth of
  the way out in the island layout. "Normal" reproduces today's 31 lines
  exactly.
- *Accent line*: when off, that line is drawn in the primary colour.

**Code rain**
- *Density*: scales the column counts of the depth planes. Suggested factors
  0.55 / 1 / 1.5.
- *Foreground streaks*: the large blurred nearest plane.

### The new Blueprint subjects

Each is a seeded orthographic front view drawn with the same line weights,
colours and lettering as the flange, fitting the same envelope (about ±480 by
±390 units around the focus point) so both layouts (`centered`, `offset`) work
unchanged. Each varies with the seed, and each has its own dimensions and
labels that obey the two switches.

- **Gear** — spur gear: toothed outline, dashed pitch circle, hub, bore with a
  keyway. Seed varies tooth count, bore size, and optional lightening holes.
  Callouts: OD, bore, "N TEETH". Title "SPUR GEAR".
- **Bearing** — ball bearing: outer race, inner race, a ring of balls, cage
  circle, bore. Seed varies ball count and race proportions. Callouts: OD,
  bore, "Nx BALLS". Title "BALL BEARING".
- **Bracket** — a rounded rectangular mounting plate with corner holes and a
  central slot or large hole; deliberately not circular, for variety. Seed
  varies plate proportions, hole count (4 or 6) and slot length. Callouts:
  width, height, "Nx MOUNT HOLES". Title "MOUNTING BRACKET".

Exact proportions and seed ranges are the builder's; they should look as
finished as the flange.

## Behaviour rules

1. **Defaults are frozen.** With every new field at its default, each style
   must consume random numbers in the same order as today and draw the same
   image.
2. **Switching a part off leaves the rest in place where the design allows.**
   This holds for: all three Blueprint switches, PCB Components, Contour Accent
   line and Lines, Code rain Foreground streaks. These parts either use no
   randomness or use it last, so skipping them is enough.
3. **Parts that shape the layout re-flow it.** PCB Hero chip, Small chips and
   Traces, and Code rain Density change where other things land for the same
   seed. That is accepted (author's call).
4. Changing the Blueprint subject gives a different drawing for the same seed;
   the grid and layout stay put.
5. Output stays deterministic for any combination of options.

## Constraints

- `RenderSpec` is a frozen, slotted dataclass loaded with
  `RenderSpec(**json.loads(spec_json))`. New fields must be flat, JSON-plain
  (str / bool) and defaulted.
- `ui/style_options.py` builds the panel from `FIELDS_BY_STYLE`; its existing
  kinds (`choice`, `check`) cover every new option. The panel is 300px wide and
  not scrollable; the PCB page grows to seven editors and must still fit the
  default 1440×900 window.
- `cli.py` must stay Qt-free.
- `tests/ui/test_style_options.py` asserts that the panel covers every style
  field and rebuilds the default spec; it needs to keep passing.

## Approaches

1. **Flat settings, switches inside the existing styles — chosen.** One new
   `RenderSpec` field per option; each style function checks its fields as it
   draws; Blueprint is split into a shared sheet plus one function per subject,
   looked up in a small dict. Fits the saved format, the field-driven panel and
   the CLI as they are. Cost: `RenderSpec` grows to about 30 fields.
2. **Registered parts.** Every style becomes a list of named parts, the spec
   stores a parts list, and the panel is generated. This is the base for
   cross-style mixing later but rewrites six styles and the saved format for a
   feature nobody has asked for. Rejected as more rewrite than necessary.
3. **A separate random sequence per part.** Makes every switch independent, but
   changes what every existing seed draws, so library entries would re-render
   as different designs. Rejected.

The owner left the how to the author; approach 1 is the author's pick.

## Shape of the change

- `engine/spec.py`: the twelve fields above, with `Literal` aliases for the
  choices (`BlueprintSubject`, `TraceDensity`, `ContourLines`, `RainDensity`).
- `engine/styles/blueprint.py`: sheet (grid, focus point, pen helpers), then a
  `_SUBJECTS` dict of subject functions. The flange moves into one unchanged in
  output. Where the subject functions live (same module or a sibling) is the
  builder's choice.
- `engine/styles/pcb.py`, `contour.py`, `coderain.py`: gate the parts.
- `ui/style_options.py`: new `Field` rows. No new widget kinds.
- `cli.py`: one flag per option in the existing per-style argument groups —
  `--blueprint-subject`, `--no-blueprint-grid`, `--no-blueprint-dimensions`,
  `--no-blueprint-labels`, `--no-hero-chip`, `--no-small-chips`, `--traces`,
  `--no-components`, `--contour-lines`, `--no-contour-accent`,
  `--rain-density`, `--no-rain-foreground`. `wallgen list` also prints the
  Blueprint subjects.
- `docs/wallgen-spec.md`: the "in-app style editor" non-goal stays, with a note
  that per-style options and built-in subjects are in scope. Update `README`
  and `CLAUDE.md` where they list options or describe adding a style.

## Testing

- **Defaults unchanged.** Before touching a style, render it at default
  settings from the current code and compare bytes with the new code on the
  same machine; this is a required step for all four styles. Keep a permanent
  regression test where it can be made stable (PCB without a wordmark, Contour,
  and Blueprint at a size small enough to skip lettering contain no text, so
  stored hashes do not depend on installed fonts). If such hashes prove
  unstable on the Windows CI runner, the builder may drop them and say so.
- Every subject renders at landscape, portrait and tiny sizes, is
  deterministic, and differs from the other subjects.
- Each switch and amount setting changes the image.
- Rule 2: with PCB Components off, or Code rain Foreground off, the remaining
  layers match the default render (for example, the off render never has more
  light than the default one, and the trace layout is identical).
- Old-row compatibility: a `spec_json` holding only the fields that exist today
  loads and equals the default-option spec.
- Panel and CLI: new fields round-trip through `values()` / `load_spec()` and
  through `spec_from_args`.

## Left to the builder

- Exact geometry, proportions and seed ranges of the three new subjects.
- Density factors and line counts, tuned by eye around the suggested values.
- Module layout for the subjects; names of internal helpers.
- Whether the default CLI output filename includes the subject.
- Field order and label wording on the panel, within the table above.
