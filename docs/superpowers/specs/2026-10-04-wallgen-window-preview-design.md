# WallGen window with preview — design

**Status:** draft, awaiting review
**Relates to:** [docs/wallgen-spec.md](../../wallgen-spec.md) §6 (UI, Threading), §7 build-order Milestone 2

## Goal

Connect the finished engine (`wallgen.engine.render` / `preview`) to the existing UI
shell, so that you can change style, palette, size, quiet zone, seed and the
style-specific text options, press Generate, and see a preview.

Done when `uv run wallgen` lets you do exactly that, with ⟳ rerolling the seed and
regenerating, and the new preview crossfading over the old one.

**Decisions made while brainstorming:**
- The style options panel becomes **editable and backed by `RenderSpec`**. The mock
  fields the engine has no knob for (Density, Depth planes, Language) are dropped.
- Generate renders **only the preview**. The background full-size render is deferred
  to Milestones 3 and 4, the first that need it.
- ⟳ **rerolls the seed and regenerates immediately**. The old preview stays visible
  until the new one crossfades in (~200 ms).

**Out of scope:**
- Full-size render, saving to disk or the library (Milestone 4).
- Setting the wallpaper (Milestone 3), real monitor detection (Milestone 5).
- Deleting the legacy root-level `wallpaper.py`. Still an open cleanup item.

## Approach

Use the threading model already specified in the main spec §6: a `QRunnable` on a
`QThreadPool` capped at 2, signals carrying results back, and cancellation by a
generation counter (stale results are dropped, not killed mid-render).

Rejected alternatives: a `QThread` worker object (more lifecycle code, no benefit
here) and `concurrent.futures` with `QTimer` polling (not idiomatic Qt, adds latency).

## Units

### `ui/jobs.py` (new)

- `pil_to_qimage(image) -> QImage`: RGB to `QImage.Format_RGB888` with an explicit
  bytes-per-line, then `.copy()` so the buffer outlives the PIL bytes. `PIL.ImageQt`
  is avoided because it is fragile across Pillow/PySide versions.
- `_JobSignals(QObject)`: `progress(int, float, str)`, `finished(int, QImage)`,
  `failed(int, str)`. The `int` is the generation.
- `RenderJob(QRunnable)`: holds `spec`, `generation`, `max_width`. `run()` calls
  `engine.preview(spec, max_width, progress=...)`, converts to `QImage` on the worker
  thread (`QImage` is thread-safe; `QPixmap` is not), and emits `finished`. Any
  exception is caught and emitted as `failed`; nothing escapes `run()`.
- `RenderController(QObject)`: owns a `QThreadPool` (`maxThreadCount=2`) and the
  generation counter.
  - `submit(spec)` bumps the counter and starts a job.
  - Re-emits only current-generation results as `preview_ready(QImage)`,
    `progress(float, str)`, `failed(str)`, and `busy_changed(bool)`.
  - Holds a Python reference to each job's signals object until it completes, so it
    is not garbage-collected mid-flight.
  - `max_width` is a constructor argument (default 1280) so tests can render tiny.

### `ui/preview_pane.py` (new)

`PreviewPane(QWidget)` replaces the inert `viewport` QFrame in `main_window.py`.

- `fit_rect(src_w, src_h, dst: QRect) -> QRect`: pure aspect-fit/letterbox geometry.
- `paintEvent` draws the current pixmap aspect-fit on the viewport background.
- `show_image(QImage)` converts to `QPixmap` on the GUI thread, then runs a
  `QVariantAnimation` (0 to 1, 200 ms) painting the old pixmap with the new one fading
  in on top.
- `show_error(msg)` overlays a short muted error line and keeps the last good image.
- Empty state shows a "Press Generate" hint.

### `ui/widgets.py`

- Add `ProgressTrack(QFrame)`: the existing 3 px track with a copper fill.
  `set_fraction(float)` sets the fill; the fill is hidden when idle. Replaces the
  inert `progress_track` frame.
- `SeedField` becomes editable: a `QLineEdit` with an int validator (0 to 2³¹−1),
  keeping the recessed monospace look. The `seed()` / `set_seed()` API is unchanged.

### `ui/style_options.py`

`_FIELDS_BY_STYLE` becomes typed field definitions (key, label, kind, placeholder):

| Style | Fields (`RenderSpec` names) | Widget |
|---|---|---|
| pcb | `mark`, `submark`, `chip_label` | `QLineEdit` |
| coderain | `glyphs` (`mixed` / `ascii`) | `QComboBox` |
| terminal | `user`, `title`; `session_text` | `QLineEdit`; `QPlainTextEdit` |
| codeblock | `caption`; `code_text`; `gutter`, `cursor` | `QLineEdit`; `QPlainTextEdit`; `QCheckBox` |

- `values() -> dict[str, object]` returns the fields of **all** pages, so edits
  survive switching styles. The engine ignores fields belonging to other styles.
- Empty text means "use the engine default" (for example empty `session_text` gives
  `DEFAULT_SESSION`). Placeholders say so.
- `set_style()` and `current_style_label()` are unchanged.

### `ui/main_window.py`

- Combos are fed from the engine, with the engine key stored as item data:
  palette from `PALETTES`, size from `SIZES` (labelled like "1440p · 2560 x 1440"),
  all five quiet-zone values, style from `STYLE_ORDER`. A test asserts `STYLE_ORDER`
  matches the engine's style set.
- `current_spec() -> RenderSpec` builds the spec from the combos, the seed field and
  `style_panel.values()`.
- Generate calls `controller.submit(current_spec())`. ⟳ rerolls the seed, then submits.
- Controller signals: `preview_ready` to `PreviewPane.show_image`, `progress` to
  `ProgressTrack.set_fraction`, `failed` to `PreviewPane.show_error`.
- Generate stays enabled during a render. The generation counter makes repeat clicks
  harmless, and parameter changes still do **not** auto-render (main spec §6).
- Module docstring updated: Generate and preview are real; monitors and library are
  still mock.

### `ui/mock_data.py`

Delete `MOCK_STYLES`, `MOCK_PALETTES`, `MOCK_SIZES`, `MOCK_QUIET_ZONES`. Keep
`MOCK_MONITORS` and `MOCK_LIBRARY` for Milestones 3 to 5. Update
`tests/ui/test_mock_data.py` and `tests/ui/test_main_window.py` to match.

## Data flow

Generate, then `current_spec()`, then `controller.submit` (generation N), then a pool
thread runs `engine.preview` and emits progress, then a `QImage` via `finished(N)`.
The controller checks N is still current, emits `preview_ready`, and
`PreviewPane.show_image` crossfades it in.

## Error handling

- An engine exception (`EngineError` or anything else) is caught in `run()` and sent
  as `failed`. The pane shows the message and keeps the last image; the progress track
  resets.
- A stale failure is dropped, like a stale success.
- An invalid seed cannot be typed, because of the validator.

## Testing

pytest-qt against the real engine with a tiny `max_width` (for example 160).

- `tests/ui/test_jobs.py`: a preview arrives as a `QImage` of the expected size; two
  quick submits yield exactly one `preview_ready` carrying the second result; a
  monkeypatched `preview` that raises yields `failed`; `busy_changed` toggles.
- `tests/ui/test_preview_pane.py`: `fit_rect` for wide, tall and equal shapes;
  `show_image` sets the pixmap and the animation finishes.
- `tests/ui/test_style_options.py`: `values()` returns all spec keys with the right
  types; edits survive a style switch.
- `tests/ui/test_main_window.py`: `current_spec()` reflects the controls; Generate
  leads to a preview showing; reroll changes the seed and triggers a render; existing
  tests adjusted for the mock removals.
- Manual: `uv run wallgen`, change style, palette and seed, press Generate, then press
  ⟳ several times quickly. Only the last preview should land, and it should crossfade.
