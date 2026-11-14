"""Command line: render wallpapers without the GUI.

    wallgen render --style pcb --size 3440x1440 --palette amber --seed 771402
    wallgen render --style terminal --script session.txt --out term.png
    wallgen list

This is how to debug the engine without a window. It imports no Qt, so it also
runs on machines with no display. The packaged WallGen.exe accepts the same
commands but, being a windowed program, has no console to print to.
"""

from __future__ import annotations

import argparse
import random
import re
import sys
from pathlib import Path
from typing import get_args

from wallgen.engine import PALETTES, SIZES, EngineError, RenderSpec, render
from wallgen.engine.spec import (
    BlueprintLayout,
    BlueprintSubject,
    ContourLayout,
    ContourLines,
    QuietZone,
    RainDensity,
    Style,
    TraceDensity,
)

COMMANDS = ("render", "list")
MAX_SEED = 2**31 - 1  # the GUI's seed field accepts the same range
# Rendering peaks at roughly 90 MB per megapixel, so 8K (33 MP) needs about
# 3 GB. Every preset and an 8K monitor fit; 16384x16384 would need ~24 GB.
MAX_PIXELS = 7680 * 4320
_SIZE = re.compile(r"(\d+)\s*[x×]\s*(\d+)", re.IGNORECASE)


def parse_size(text: str) -> tuple[int, int]:
    """A preset name ('4k') or explicit 'WIDTHxHEIGHT' ('3440x1440')."""
    if text.lower() in SIZES:
        return SIZES[text.lower()]
    match = _SIZE.fullmatch(text.strip())
    if match is None:
        raise argparse.ArgumentTypeError(
            f"{text!r} is not WIDTHxHEIGHT or a preset (see `wallgen list`)"
        )
    width, height = int(match.group(1)), int(match.group(2))
    if not (16 <= width <= 16384 and 16 <= height <= 16384):
        raise argparse.ArgumentTypeError(f"{width}x{height} is outside 16..16384 per side")
    if width * height > MAX_PIXELS:
        raise argparse.ArgumentTypeError(
            f"{width}x{height} is {width * height / 1e6:.0f} megapixels; the limit is "
            f"{MAX_PIXELS / 1e6:.0f} (8K), which already needs about 3 GB of memory"
        )
    return width, height


def _seed(text: str) -> int:
    try:
        seed = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a whole number") from None
    if not 0 <= seed <= MAX_SEED:
        raise argparse.ArgumentTypeError(f"seed must be between 0 and {MAX_SEED}")
    return seed


def _text_file(text: str) -> str:
    try:
        return Path(text).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise argparse.ArgumentTypeError(f"cannot read {text}: {exc}") from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wallgen",
        description="Procedural desktop wallpapers. Run with no command to open the window.",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    commands.add_parser("list", help="print every size preset, palette and style")

    r = commands.add_parser(
        "render", help="render one wallpaper to a PNG",
        description="Render one wallpaper to a PNG. The same options and seed always "
                    "produce the same image.",
    )
    r.add_argument("--style", default="pcb", choices=get_args(Style))
    r.add_argument("--size", type=parse_size, default="1440p", metavar="SIZE",
                   help="WIDTHxHEIGHT or a preset name (default: 1440p)")
    r.add_argument("--palette", default="cyber", choices=list(PALETTES))
    r.add_argument("--seed", type=_seed, default=None,
                   help="omit for a random layout; the seed used is printed")
    r.add_argument("--quiet-zone", default="left", choices=get_args(QuietZone),
                   help="edge kept darker so desktop icons stay readable (default: left)")
    r.add_argument("--out", type=Path, default=None,
                   help="output PNG (default: wallpaper-STYLE-WxH-SEED.png here)")

    pcb = r.add_argument_group("pcb")
    pcb.add_argument("--mark", default="", help="wordmark text, e.g. 'J A M I E'")
    pcb.add_argument("--submark", default="", help="small line under the wordmark")
    pcb.add_argument("--chip-label", default="", help="text on the hero chip")
    pcb.add_argument("--traces", dest="pcb_traces", default="normal",
                     choices=get_args(TraceDensity), help="how many traces are routed")
    pcb.add_argument("--no-hero-chip", dest="pcb_hero_chip", action="store_false",
                     help="leave out the large chip")
    pcb.add_argument("--no-small-chips", dest="pcb_small_chips", action="store_false",
                     help="leave out the four smaller chips")
    pcb.add_argument("--no-components", dest="pcb_components", action="store_false",
                     help="leave out the small pads and dots")

    rain = r.add_argument_group("coderain")
    rain.add_argument("--glyphs", default="mixed", choices=["mixed", "ascii"])
    rain.add_argument("--rain-density", default="normal", choices=get_args(RainDensity),
                      help="how many columns of rain fall")
    rain.add_argument("--no-rain-foreground", dest="rain_foreground", action="store_false",
                      help="leave out the large blurred streaks in front")

    term = r.add_argument_group("terminal")
    term.add_argument("--user", default="you@localhost", help="shell prompt name")
    term.add_argument("--title", default="", help="window title bar text")
    term.add_argument("--script", type=_text_file, default=None, metavar="FILE",
                      help="session file: '$ cmd' lines, '[ok] msg' status lines, output")

    code = r.add_argument_group("codeblock")
    code.add_argument("--code", type=_text_file, default=None, metavar="FILE", help="code file to show")
    code.add_argument("--caption", default="", help="small line under the code")
    code.add_argument("--no-gutter", dest="gutter", action="store_false", help="hide line numbers")
    code.add_argument("--no-cursor", dest="cursor", action="store_false", help="hide the cursor block")

    defaults = RenderSpec()
    blueprint = r.add_argument_group("blueprint")
    blueprint.add_argument("--blueprint-layout", choices=get_args(BlueprintLayout),
                           default=defaults.blueprint_layout)
    blueprint.add_argument("--blueprint-subject", choices=get_args(BlueprintSubject),
                           default=defaults.blueprint_subject, help="what the drawing shows")
    blueprint.add_argument("--no-blueprint-grid", dest="blueprint_grid", action="store_false",
                           help="leave out the drafting grid")
    blueprint.add_argument("--no-blueprint-dimensions", dest="blueprint_dimensions",
                           action="store_false", help="leave out dimension lines and callouts")
    blueprint.add_argument("--no-blueprint-labels", dest="blueprint_labels",
                           action="store_false", help="leave out the title and view caption")
    contour = r.add_argument_group("contour")
    contour.add_argument("--contour-layout", choices=get_args(ContourLayout),
                         default=defaults.contour_layout)
    contour.add_argument("--contour-lines", choices=get_args(ContourLines),
                         default=defaults.contour_lines, help="how many contour lines")
    contour.add_argument("--no-contour-accent", dest="contour_accent", action="store_false",
                         help="draw the accent line in the main colour")
    return parser


def spec_from_args(args: argparse.Namespace) -> RenderSpec:
    width, height = args.size
    return RenderSpec(
        style=args.style, width=width, height=height, palette=args.palette,
        seed=args.seed if args.seed is not None else random.randint(0, 99_999_999),
        quiet_zone=args.quiet_zone,
        mark=args.mark, submark=args.submark, chip_label=args.chip_label,
        # Empty text selects the style's built-in sample session or code.
        user=args.user, title=args.title, session_text=args.script or "",
        code_text=args.code or "", caption=args.caption,
        glyphs=args.glyphs, gutter=args.gutter, cursor=args.cursor,
        blueprint_layout=args.blueprint_layout, contour_layout=args.contour_layout,
        blueprint_subject=args.blueprint_subject, blueprint_grid=args.blueprint_grid,
        blueprint_dimensions=args.blueprint_dimensions, blueprint_labels=args.blueprint_labels,
        pcb_hero_chip=args.pcb_hero_chip, pcb_small_chips=args.pcb_small_chips,
        pcb_traces=args.pcb_traces, pcb_components=args.pcb_components,
        contour_lines=args.contour_lines, contour_accent=args.contour_accent,
        rain_density=args.rain_density, rain_foreground=args.rain_foreground,
    )


def _print(text: str = "", stream=None) -> None:
    stream = stream if stream is not None else sys.stdout
    if stream is not None:  # None in the windowed WallGen.exe
        print(text, file=stream)


def _list() -> int:
    _print("SIZES")
    for key, (w, h) in sorted(SIZES.items(), key=lambda item: -item[1][0] * item[1][1]):
        _print(f"  {key:<15} {w}x{h}  ({w / h:.2f}:1)")
    _print("\nPALETTES\n  " + "  ".join(PALETTES))
    _print("\nSTYLES\n  " + "  ".join(get_args(Style)))
    _print("\nBLUEPRINT SUBJECTS\n  " + "  ".join(get_args(BlueprintSubject)))
    return 0


def _progress_printer():
    """A one-line progress readout on an interactive terminal; silent otherwise."""
    stream = sys.stderr
    if stream is None or not stream.isatty():
        return None, lambda: None

    def show(fraction: float, note: str) -> None:
        stream.write(f"\r  {fraction:4.0%}  {note:<40.40}")
        stream.flush()

    def clear() -> None:
        stream.write("\r" + " " * 50 + "\r")
        stream.flush()

    return show, clear


def _render(args: argparse.Namespace) -> int:
    spec = spec_from_args(args)
    name = spec.style
    if spec.style == "blueprint":
        if spec.blueprint_subject != RenderSpec().blueprint_subject:
            name = f"{name}-{spec.blueprint_subject}"
        name = f"{name}-{spec.blueprint_layout}"
    elif spec.style == "contour":
        name = f"{name}-{spec.contour_layout}"
    out = args.out or Path(f"wallpaper-{name}-{spec.width}x{spec.height}-{spec.seed}.png")
    show, clear = _progress_printer()
    try:
        image = render(spec, progress=show)
    except EngineError as exc:
        clear()
        _print(f"wallgen: render failed: {exc}", sys.stderr)
        return 1
    except MemoryError:
        clear()
        _print(f"wallgen: ran out of memory rendering {spec.width}x{spec.height}; "
               "try a smaller size", sys.stderr)
        return 1
    clear()
    try:
        image.save(out, format="PNG", optimize=True)
    except OSError as exc:
        _print(f"wallgen: cannot write {out}: {exc}", sys.stderr)
        return 1
    _print(f"{out}  {spec.width}x{spec.height}  style={spec.style} "
           f"palette={spec.palette} seed={spec.seed}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run a command; `argv` excludes the program name."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # --help, or a usage error already explained
        return exc.code if isinstance(exc.code, int) else 2
    return _list() if args.command == "list" else _render(args)
