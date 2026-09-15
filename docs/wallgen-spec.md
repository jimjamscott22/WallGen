# WallGen — plan & spec

A Windows desktop app that generates wallpapers with the engine you already have,
keeps every render in a searchable library, and sets them per monitor.

| Decision | Choice | Why |
|---|---|---|
| Stack | Python 3.12 + PySide6 6.11 | The engine is already Python. A port is weeks; a GUI shell is evenings. |
| Package manager | `uv` | Lockfile, fast installs, `uv run` as the single entry point |
| v1 scope | Generate + set, library, per-monitor | Deliberately no tray/scheduler — see §10 |
| Emphasis | Personal tool, ship fast | Minimal layers. One abstraction only where it buys thread safety |

**Definition of done for v1:** you open WallGen, click Generate a few times until you
like one, hit Set on monitor 1, and close it. Everything you've ever generated is
still there tomorrow, re-renderable at any size.

---

## 1. What v1 is, and what it isn't

**In:**

- Generate a wallpaper from style + palette + size + seed, with a live preview
- Re-roll the seed; tweak params and re-render
- Set as wallpaper — all monitors, or one specific monitor
- Every render auto-saved to a library with its full spec; browse, favorite, delete
- Re-render any library item at a different resolution (this is what seeds are *for*)
- Detect connected monitors and offer their native resolutions as one-click sizes

**Out, on purpose:**

- Tray app and scheduled rotation → v2. It doubles the surface area (background
  process, autostart, notification handling) for zero benefit while you're still
  deciding whether you like the app.
- Cloud anything, accounts, sync
- An in-app style editor. Styles are code; adding one is a Python function.
- Cross-platform. `win32` only; the platform layer is isolated so that's a
  one-file problem later, not an architecture problem.

---

## 2. Architecture

One rule, and it's the only one that matters: **the engine knows nothing about Qt,
and nothing about Windows.** It takes a spec, returns a `PIL.Image`. Everything
else is a shell around that. Break this and threading and testing both get ugly.

```
wallgen/
├─ engine/              pure render. no Qt, no win32, no disk writes
│   ├─ spec.py          RenderSpec dataclass, palettes, size presets
│   ├─ ctx.py           Ctx: scale, quiet zone, rng, layers
│   ├─ common.py        finish(), glow(), base_gradient(), fonts
│   └─ styles/          pcb.py  coderain.py  terminal.py  codeblock.py
├─ store/
│   ├─ db.py            SQLite: schema, migrations, queries
│   └─ paths.py         %LOCALAPPDATA%\WallGen\{library,thumbs,wallpapers.db}
├─ platform_win/
│   ├─ desktop.py       IDesktopWallpaper COM + SystemParametersInfoW fallback
│   └─ monitors.py      enumerate displays, map Qt screens ↔ COM monitor IDs
├─ ui/
│   ├─ main_window.py   the single window
│   ├─ panels.py        ParamPanel, PreviewPane, LibraryGrid, MonitorBar
│   └─ jobs.py          QThreadPool wrappers around engine.render
└─ __main__.py          uv run wallgen
```

Dependency direction is strictly downward: `ui → store, platform_win, engine`;
`store → engine` (for the spec type only); `engine → nothing of ours`.

```
pyproject.toml deps:
  pyside6 >= 6.11        GUI (LGPL — fine for a personal tool, and for shipping
                         a non-modified dynamically-linked build)
  pillow >= 11           already a dependency of the engine
  numpy >= 2             same
  comtypes >= 1.4        COM interop for IDesktopWallpaper
dev:
  pytest, ruff
```

---

## 3. Step one: turn the script into a library

The existing `wallpaper.py` is ~810 lines and already structured correctly — four
`render_*(ctx, a)` functions that return a `PIL.Image`, with `img.save()` living in
`main()` rather than inside the renderers. The refactor is mostly mechanical. Five
real changes:

**3.1 Replace the argparse namespace with a dataclass.** The render functions read
`a.mark`, `a.chip_label`, `a.session_text`, `a.glyphs`, `a.gutter`, and friends. Give
`RenderSpec` those exact field names and the bodies need no edits at all — you just
pass `spec` where `a` went.

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
        return replace(self, width=w, height=h)     # same design, new screen
```

Frozen + `slots` because a spec is an identity: it goes in the DB, gets hashed, and
must never be mutated by a renderer.

**3.2 Kill the global RNG.** `Ctx.__init__` currently calls `random.seed(self.seed)`
and every renderer calls the module-level `random.*` (roughly 60 call sites). That is
a hidden global. Two concurrent renders — which you *will* have the moment the UI
renders a preview while a full-size render is running — interleave draws from one
shared sequence and both come out wrong, non-reproducibly.

Fix: `self.rng = random.Random(spec.seed)` on `Ctx`, then a mechanical
`random.` → `ctx.rng.` sweep inside the style modules. `np.random.default_rng(seed)`
in `finish()` is already per-call and needs no change.

Verify it worked with a test, because this is the one bug that silently corrupts
output rather than crashing:

```python
def test_render_is_deterministic_under_concurrency():
    spec = RenderSpec(style="pcb", width=640, height=360, seed=7)
    once = render(spec).tobytes()
    with ThreadPoolExecutor(4) as ex:
        results = [f.result().tobytes() for f in
                   [ex.submit(render, spec) for _ in range(4)]]
    assert all(r == once for r in results)
```

**3.3 Make font resolution lazy and non-fatal.** The script resolves fonts at import
and calls `sys.exit()` if none are found. A GUI whose import can terminate the process
is a bad time. Move it into a cached function that raises `EngineError`.

While you're in there — **add Windows CJK fonts to the candidate list.** Right now the
CJK candidates are all Linux paths, so on your machine `coderain` silently falls back
to ASCII-only and doesn't look like the render you approved:

```python
"cjk": [..., "C:/Windows/Fonts/YuGothR.ttc",
             "C:/Windows/Fonts/meiryo.ttc",
             "C:/Windows/Fonts/msgothic.ttc"],
```

**3.4 Add a progress callback.** A 4K PCB render is ~20s. The UI needs to show
something. Thread an optional `progress(fraction: float, note: str)` through the
scatter loops — three or four call sites per style is plenty of granularity.

**3.5 Add `preview()`.** Because every constant scales from `min(W,H)/1440`, a
half-size render is genuinely the same composition rather than an approximation —
so the preview is honest, and it's ~4x faster.

```python
def preview(spec, max_width=1280):
    scale = min(1.0, max_width / spec.width)
    return render(spec.at(round(spec.width * scale), round(spec.height * scale)))
```

**Keep the CLI.** `wallgen render --style pcb ...` as a second entry point costs
nothing once the library exists, and it's how you'll debug the engine without
launching a GUI.

---

## 4. The Windows part

Two APIs. Use both.

`SystemParametersInfoW(SPI_SETDESKWALLPAPER, ...)` is the ancient one: sets the same
image everywhere, works on everything, four lines of ctypes. Keep it as the fallback.

`IDesktopWallpaper` (Windows 8+, `shobjidl_core.h`) is the real one: per-monitor
images, fit mode, monitor enumeration with stable IDs.

```python
CLSID_DesktopWallpaper = GUID("{C2CF3110-460E-4FC1-B9D0-8A1C0C9CC4BD}")
IID_IDesktopWallpaper  = GUID("{B92B56A9-8B55-4E14-9A89-0199BBB6F93B}")
```

Declare the interface with `comtypes.COMMETHOD` in **exact IDL vtable order** —
`SetWallpaper, GetWallpaper, GetMonitorDevicePathAt, GetMonitorDevicePathCount,
GetMonitorRECT, SetBackgroundColor, GetBackgroundColor, SetPosition, GetPosition, …`
Order is load-bearing: comtypes indexes the vtable by position, so a method inserted
in the wrong place calls the wrong function with your arguments. Declaring only the
first nine is fine as long as you never call past `GetPosition`.

```python
class IDesktopWallpaper(IUnknown):
    _iid_ = IID_IDesktopWallpaper
    _methods_ = [
        COMMETHOD([], HRESULT, "SetWallpaper",
                  (["in"], c_wchar_p, "monitorID"),
                  (["in"], c_wchar_p, "wallpaper")),
        COMMETHOD([], HRESULT, "GetWallpaper",
                  (["in"], c_wchar_p, "monitorID"),
                  (["out"], POINTER(c_wchar_p), "wallpaper")),
        COMMETHOD([], HRESULT, "GetMonitorDevicePathAt",
                  (["in"], UINT, "monitorIndex"),
                  (["out"], POINTER(c_wchar_p), "monitorID")),
        COMMETHOD([], HRESULT, "GetMonitorDevicePathCount",
                  (["out"], POINTER(UINT), "count")),
        COMMETHOD([], HRESULT, "GetMonitorRECT",
                  (["in"], c_wchar_p, "monitorID"),
                  (["out"], POINTER(RECT), "displayRect")),
        # SetBackgroundColor / GetBackgroundColor / SetPosition / GetPosition …
    ]
```

Fit mode is `SetPosition(DESKTOP_WALLPAPER_POSITION)`:
`CENTER=0, TILE=1, STRETCH=2, FIT=3, FILL=4, SPAN=5`. You always want **FILL (4)** —
you're generating at native resolution, so nothing should scale, but FILL is the
graceful failure if the monitor changes resolution behind you.

### The gotcha that will eat an evening

`GetMonitorDevicePathAt` returns opaque strings like `\\?\DISPLAY#GSM5B08#5&...`.
Qt's `QScreen.name()` returns `\\.\DISPLAY1`. **They do not match and there is no
documented mapping.** So don't try to match by name — match by geometry:

1. `GetMonitorRECT(device_path)` → virtual-desktop rect in **physical** pixels
2. `QScreen.geometry()` → same rect in **logical** pixels
3. Multiply the Qt rect by `QScreen.devicePixelRatio()`, then match on top-left corner

Two more things in the same neighborhood:

- **Ask Windows for the real resolution.** Qt reports logical size, so on a 150%-scaled
  display a 2560x1440 monitor reports 1707x960. Generating at *that* is the classic
  blurry-wallpaper bug. Always generate at the physical size from `GetMonitorRECT`.
- **Set DPI awareness before the QApplication exists**, or the numbers lie from the
  start: `ctypes.windll.shcore.SetProcessDpiAwareness(2)` as the first line of
  `__main__.py`.

### COM threading

COM is apartment-bound. If you call `SetWallpaper` from a worker thread, that thread
needs its own `CoInitialize()` and its own object instance — you cannot construct the
COM object on the main thread and use it elsewhere. Simplest correct answer for v1:
**do all wallpaper-setting on the main thread.** It's a sub-millisecond call; it
doesn't need a thread. Only rendering goes to the pool.

### Windows also caches

Windows copies your image to `%APPDATA%\Microsoft\Windows\Themes\TranscodedWallpaper`
and re-encodes it as JPEG. Two consequences: setting the same path twice may not
visibly refresh, and the desktop shows a slightly lossier image than your PNG. Work
around the first by writing each render to a unique filename in the library — which
you're doing anyway.

---

## 5. Data model

Files in `%LOCALAPPDATA%\WallGen\`:

```
library\<id>.png          full-resolution render
thumbs\<id>.jpg           480px wide, for the grid
wallgen.db                SQLite
```

```sql
CREATE TABLE wallpaper (
    id          TEXT PRIMARY KEY,     -- uuid4 hex, also the filename
    created_at  TEXT NOT NULL,        -- ISO 8601
    style       TEXT NOT NULL,
    palette     TEXT NOT NULL,
    width       INTEGER NOT NULL,
    height      INTEGER NOT NULL,
    seed        INTEGER NOT NULL,
    spec_json   TEXT NOT NULL,        -- the full RenderSpec; source of truth
    favorite    INTEGER NOT NULL DEFAULT 0,
    last_set_at TEXT                  -- null = never used as a wallpaper
);
CREATE INDEX idx_wallpaper_created  ON wallpaper(created_at DESC);
CREATE INDEX idx_wallpaper_favorite ON wallpaper(favorite, created_at DESC);

CREATE TABLE preset (                 -- saved parameter sets, not images
    name       TEXT PRIMARY KEY,
    spec_json  TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

`spec_json` is the point of the whole schema. The denormalized columns exist only so
you can filter and sort without parsing JSON; the JSON is what actually reproduces
the image. "Re-render at 3440x1440" is `RenderSpec(**json.loads(row.spec_json)).at(3440, 1440)`.

Migrations: one `PRAGMA user_version` integer and a list of migration functions.
Don't reach for Alembic on a single-user SQLite file.

---

## 6. UI

One window, three regions. No tabs, no wizard, no modal dialogs except the file picker.

```
┌──────────────────────────────────────────────────────────────────────┐
│  Style [PCB ▾]  Palette [cyber ▾]  Size [2560x1440 ▾]  Quiet [left ▾]│
│  Seed [ 20260813 ] [⟳]                        [ Generate ]            │
├───────────────────────────────────┬──────────────────────────────────┤
│                                   │  Mark      [ J A M I E        ]  │
│                                   │  Submark   [ BUILD 2560x1440  ]  │
│         preview                   │  Chip      [ JMI-1440         ]  │
│    (aspect-correct, letterboxed)  │                                  │
│                                   │  ── style-specific; this panel   │
│         [progress bar]            │     swaps with the style ──      │
│                                   │                                  │
├───────────────────────────────────┴──────────────────────────────────┤
│  Set on:  [ All ]  [ ▣ DELL 2560x1440 ]  [ ▣ LG 1920x1080 ]          │
├──────────────────────────────────────────────────────────────────────┤
│  Library   [ ▣ ][ ▣ ][ ▣ ][ ▣ ][ ▣ ][ ▣ ]   ☆ favorites only  🔍     │
└──────────────────────────────────────────────────────────────────────┘
```

Interactions worth specifying because they're where the feel lives:

- **Generate** renders a preview first (~1–2s), shows it, then quietly renders full
  size in the background and swaps the library thumbnail in when done. You're never
  waiting 20 seconds to find out you don't like the layout.
- **⟳** next to Seed randomizes and immediately re-generates. This is the button you
  will press the most. Make it satisfying: keep the old preview visible, fade in the
  new one.
- **Set on:** the monitor chips show real detected displays with their real
  resolutions. Clicking one renders the current spec *at that monitor's size* if it
  isn't already, then sets it there.
- **Library** double-click loads that spec back into the controls. Right-click →
  favorite / re-render at… / open folder / delete.
- Param changes do **not** auto-render. Explicit Generate. Auto-render on every
  spinbox tick is how you end up with a thrashing thread pool.

### Threading

Exactly one rule: **`engine.render` never runs on the GUI thread.** Wrap it in a
`QRunnable` on a `QThreadPool` capped at 2. A `QObject` signal carries the finished
`PIL.Image` back; convert to `QPixmap` on the main thread.

```python
class RenderJob(QRunnable):
    def __init__(self, spec, on_done, on_progress):
        super().__init__()
        self.signals = _Signals()          # QObject holding finished/progress
        ...
    def run(self):
        try:
            img = render(self.spec, progress=self.signals.progress.emit)
            self.signals.finished.emit(img)
        except Exception as e:              # never let an exception escape run()
            self.signals.failed.emit(str(e))
```

Generation is cancel-by-generation-counter: each Generate bumps an int, and results
tagged with a stale counter are dropped rather than displayed. Simpler and more
robust than trying to actually kill a render mid-numpy.

---

## 7. Build order

Each milestone ends with something you can run. Estimates assume evenings, not days.

| # | Milestone | Done when | Est. |
|---|---|---|---|
| 1 | **Skeleton + engine as library** — `uv init`, package layout, §3 refactor, determinism test passes | `uv run python -c "from wallgen.engine import render, RenderSpec; render(RenderSpec()).save('x.png')"` works | 1–2 |
| 2 | **Window with preview** — controls, RenderJob, preview pane, progress | You can change style/palette/seed and see a preview | 2 |
| 3 | **Set wallpaper** — `SystemParametersInfoW` only, all monitors | The button actually changes your desktop | 1 |
| 4 | **Library** — SQLite, auto-save, thumbnail grid, load-back, favorite, delete | Yesterday's renders are still there | 2 |
| 5 | **Per-monitor** — COM interface, geometry matching, monitor chips, per-monitor set | Different wallpaper on each screen | 2 |
| 6 | **Package** — PyInstaller, icon, first-run folder creation | `WallGen.exe` runs on a machine without Python | 1 |

Ship after 3 if you want something usable this week; 4–6 are each independently
valuable and none of them block each other.

Do milestone 5 **last among the features** despite it being the interesting one. It's
the only part that can't be debugged in this container, and the only part where a
mistake is a silent misbehavior rather than a traceback.

---

## 8. Packaging

```bash
uv run pyinstaller --noconsole --onedir --name WallGen \
    --icon assets/wallgen.ico \
    --collect-submodules comtypes \
    src/wallgen/__main__.py
```

- `--onedir`, not `--onefile`. One-file unpacks to a temp dir on every launch, which
  adds seconds to startup for a 60–80MB PySide6 bundle and confuses relative paths.
- `--collect-submodules comtypes` because comtypes generates wrapper modules at
  runtime and PyInstaller's static analysis misses them. Missing this is the classic
  "works in dev, ImportError in the build" failure.
- Exclude the PySide6 modules you don't use (`QtWebEngine`, `Qt3D`, `QtCharts`,
  `QtMultimedia`) — that's most of the bundle size.
- Bundle a CJK font (or accept the ASCII fallback) if you want `coderain` to look
  right on a machine without Japanese fonts installed.
- Don't sign it. You're the only user; SmartScreen will warn once and you click through.

---

## 9. Gotchas, collected

1. Global `random` → per-spec `Random` instance, or concurrent renders corrupt
   each other silently. The single most important line in this document.
2. Qt logical pixels ≠ physical pixels on scaled displays. Set DPI awareness first,
   generate at physical size.
3. Qt screen names and COM monitor IDs don't match. Match by geometry.
4. comtypes vtable order must match the IDL exactly.
5. COM objects are apartment-bound — build and use them on the same thread.
6. Windows re-encodes your wallpaper to JPEG in its own cache; unique filenames
   sidestep the refresh problem.
7. Never let an exception escape `QRunnable.run()` — it takes the app with it.
8. `PIL.ImageFont.truetype` sizes must be int; the engine already coerces, keep that.
9. Module-level `sys.exit()` in a library is a landmine. Raise instead.

---

## 10. v2 parking lot

In rough order of value-per-evening:

- **Tray + auto-rotate.** `QSystemTrayIcon`, a `QTimer`, and a rotation source
  (favorites pool, or generate-fresh). Autostart via a shortcut in `shell:startup`
  rather than a registry Run key — easier to reason about and to undo.
- **Export a matching set** — one spec rendered for desktop, phone, and lock screen
  in one click. The `at()` method already does the work.
- **New styles** — each is one `render_*` function and one dict entry. The isometric
  server rack and topographic contour ideas from the build log land here.
- **Animated wallpapers** — the code rain and terminal cursor are the candidates,
  and your wallpaper folder already has two `.mp4`s, so the setup supports them.
  This means a frame loop and an encoder, not a new renderer.
- **Import a reference image** and derive a palette from it — closes the loop with
  how this project started.
