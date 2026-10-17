# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Project uses `uv` (Python >=3.12, src layout, hatchling). A `.venv` is checked out locally.

```bash
uv sync                                   # install deps incl. dev group (pytest, pytest-qt)
uv run wallgen                            # launch the PySide6 GUI (wallgen.__main__:main)
uv run pytest                             # full suite
uv run pytest tests/engine/test_style_pcb.py::test_name   # single test
uv run pytest tests/ui                    # one area (engine / ui / store tests)
```

No linter or formatter is configured. `tests/conftest.py` forces `QT_QPA_PLATFORM=offscreen` and redirects `LOCALAPPDATA` to a tmp dir per test, so tests never touch the real library — keep that isolation when adding tests that write to disk.

## Searching

For any file search or grep in the current git-indexed directory, use fff tools (`mcp__fff__find_files`, `mcp__fff__grep`, `mcp__fff__multi_grep`).

## Architecture

Windows-only desktop app: seeded procedural wallpaper generator. Four layers under `src/wallgen/`, with strict one-way dependencies:

- **`engine/`** — pure rendering. No Qt, no win32, no disk writes. `engine.render(spec)` / `engine.preview(spec, max_width)` take a frozen `RenderSpec` (`engine/spec.py`, also holds `SIZES` and `PALETTES`) and return a `PIL.Image`. `render` builds a `Ctx` (`engine/ctx.py`) and dispatches via the `_STYLES` dict in `engine/__init__.py` to one function per style in `engine/styles/` (`pcb`, `coderain`, `terminal`, `codeblock`). Adding a style means a new module there, a `Style` literal entry in `spec.py`, and a `_STYLES` entry.
- **`store/`** — persistence. `LibraryStore` (`store/db.py`) is SQLite (`user_version` schema migration, one connection per operation so worker threads are safe); `store/paths.py` resolves `%LOCALAPPDATA%\WallGen` (`library/` PNGs, `thumbs/`, `wallgen.db`).
- **`platform_win/`** — Windows wallpaper setting (`desktop.py`, ctypes `SystemParametersInfoW`; sets one image on all monitors).
- **`ui/`** — PySide6 window (`main_window.py`) plus panels/widgets. `ui/jobs.py` is the bridge to the engine: `RenderController` runs `RenderJob`s on a `QThreadPool` (max 2 threads), emits a half-size preview first then the full render, and drops stale results by a generation counter (every `submit()`/`load()`/`invalidate()` bumps it). Nothing from engine/disk work may run on the GUI thread; `RenderJob.run` catches all exceptions and reports them via the `failed` signal.

### Key design invariants

- **A wallpaper is its `RenderSpec` + integer seed.** The library stores the full spec as JSON (`spec_json`) and the PNG is just a cache; `spec.at(w, h)` re-cuts the same design at another size. Output must be deterministic for a given spec (`Ctx.rng = random.Random(spec.seed)`; see `tests/engine/test_determinism.py`). Don't use unseeded randomness in styles. Adding a field to `RenderSpec` must keep old `spec_json` rows loadable (`RenderSpec(**json)`).
- **All style constants are in "units"** = 1px at 1440p, scaled by `Ctx.U = min(W,H)/1440` (`ctx.u(v)`). `Ctx.S` is a supersample factor capped by a ~24MP budget (`ctx.s(v)`, `ctx.layer()`). Don't hard-code pixel values in styles.
- **Quiet zone**: `Ctx.quiet()` / `quiet_mask()` darken one edge so desktop icons stay legible; styles must honor `spec.quiet_zone`.
- Progress is reported as `progress(fraction, note)` callbacks passed through `render`/`preview`.

## Docs and project state

- Work proceeds in milestones; design specs and plans live in `docs/superpowers/{specs,plans}/` and the overall product spec in `docs/wallgen-spec.md`. Milestones 3 (live threaded preview + full-res render) and 4 (library) are implemented; per-monitor selection (M5) is planned.
- `README.md` describes some things not yet implemented: the `wallgen render` / `wallgen list` CLI (current `__main__` only launches the GUI), per-monitor wallpapers via `IDesktopWallpaper` COM (current code uses `SystemParametersInfoW`), and a `comtypes` dependency (not in `pyproject.toml`). Treat the code as the source of truth.
- `.claude/hooks/conventional-commits.py` is a no-op PreToolUse stub; commits in history follow Conventional Commits (`feat:`, `fix:`).
