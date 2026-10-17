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
from wallgen.engine.spec import QuietZone, Style

COMMANDS = ("render", "list")
MAX_SEED = 2**31 - 1  # the GUI's seed field accepts the same range
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

    rain = r.add_argument_group("coderain")
    rain.add_argument("--glyphs", default="mixed", choices=["mixed", "ascii"])

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
    out = args.out or Path(f"wallpaper-{spec.style}-{spec.width}x{spec.height}-{spec.seed}.png")
    show, clear = _progress_printer()
    try:
        image = render(spec, progress=show)
    except EngineError as exc:
        clear()
        _print(f"wallgen: render failed: {exc}", sys.stderr)
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
