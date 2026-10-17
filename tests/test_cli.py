import io
import subprocess
import sys

import pytest
from PIL import Image

import wallgen.__main__ as wallgen_main
from wallgen import cli
from wallgen.engine import PALETTES, SIZES, EngineError, RenderSpec, render


@pytest.fixture
def here(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run(capsys, *args):
    code = cli.main(list(args))
    out, err = capsys.readouterr()
    return code, out, err


@pytest.mark.parametrize("text, size", [
    ("4k", (3840, 2160)), ("UW-1440", (3440, 1440)), ("3440x1440", (3440, 1440)),
    ("1920X1080", (1920, 1080)), ("2560 × 1440", (2560, 1440)),
])
def test_sizes_accept_presets_and_dimensions(text, size):
    assert cli.parse_size(text) == size


@pytest.mark.parametrize("text", ["99", "wide", "0x100", "100x-5", "20000x1080", "1920x1080x2"])
def test_bad_sizes_are_usage_errors(capsys, text):
    code, _, err = run(capsys, "render", "--size", text)
    assert code == 2
    assert "--size" in err


@pytest.mark.parametrize("seed", ["-1", "2147483648", "seven"])
def test_bad_seeds_are_usage_errors(capsys, seed):
    code, _, err = run(capsys, "render", "--seed", seed)
    assert code == 2 and "--seed" in err


def test_list_prints_every_size_palette_and_style(capsys):
    code, out, _ = run(capsys, "list")
    assert code == 0
    for key, (w, h) in SIZES.items():
        assert f"{key}" in out and f"{w}x{h}" in out
    assert all(palette in out for palette in PALETTES)
    assert all(style in out for style in ("pcb", "coderain", "terminal", "codeblock"))


def test_every_flag_reaches_the_spec(tmp_path):
    session, code = tmp_path / "session.txt", tmp_path / "code.py"
    session.write_text("$ ls\n[ok] fine\n", encoding="utf-8")
    code.write_text("print('hi')\n", encoding="utf-8")
    args = cli.build_parser().parse_args([
        "render", "--style", "codeblock", "--size", "uw-1440", "--palette", "ice",
        "--seed", "42", "--quiet-zone", "none", "--mark", "M", "--submark", "S",
        "--chip-label", "C", "--glyphs", "ascii", "--user", "u@h", "--title", "T",
        "--script", str(session), "--code", str(code), "--caption", "cap",
        "--no-gutter", "--no-cursor",
    ])
    assert cli.spec_from_args(args) == RenderSpec(
        style="codeblock", width=3440, height=1440, palette="ice", seed=42,
        quiet_zone="none", mark="M", submark="S", chip_label="C", glyphs="ascii",
        user="u@h", title="T", session_text="$ ls\n[ok] fine\n", code_text="print('hi')\n",
        caption="cap", gutter=False, cursor=False,
    )


def test_defaults_match_the_engine_defaults_apart_from_the_random_seed():
    spec = cli.spec_from_args(cli.build_parser().parse_args(["render", "--seed", "0"]))
    assert spec == RenderSpec()


def test_render_writes_the_exact_engine_image_with_a_default_name(capsys, here):
    code, out, _ = run(capsys, "render", "--style", "terminal", "--size", "320x180", "--seed", "7")
    assert code == 0
    path = here / "wallpaper-terminal-320x180-7.png"
    assert out.strip() == f"{path.name}  320x180  style=terminal palette=cyber seed=7"
    expected = render(RenderSpec(style="terminal", width=320, height=180, seed=7))
    with Image.open(path) as saved:
        assert saved.tobytes() == expected.tobytes()


def test_omitted_seed_is_random_and_reported(capsys, here):
    code, out, _ = run(capsys, "render", "--style", "codeblock", "--size", "320x180", "--out", "x.png")
    assert code == 0
    seed = int(out.split("seed=")[1])
    assert 0 <= seed <= cli.MAX_SEED
    assert (here / "x.png").is_file()


def test_missing_script_file_is_a_usage_error(capsys, here):
    code, _, err = run(capsys, "render", "--style", "terminal", "--script", "nope.txt")
    assert code == 2 and "cannot read nope.txt" in err


def test_engine_errors_exit_1_with_a_message(capsys, here, monkeypatch):
    def broken(spec, progress=None):
        raise EngineError("no usable font found")

    monkeypatch.setattr(cli, "render", broken)
    code, out, err = run(capsys, "render", "--size", "320x180")
    assert code == 1
    assert "render failed: no usable font found" in err
    assert out == ""


def test_unwritable_output_exits_1(capsys, here):
    code, _, err = run(capsys, "render", "--size", "320x180", "--style", "terminal",
                       "--out", str(here / "missing-dir" / "x.png"))
    assert code == 1 and "cannot write" in err


def test_progress_shows_only_on_an_interactive_terminal(here, monkeypatch, capsys):
    class Tty(io.StringIO):
        def isatty(self):
            return True

    tty = Tty()
    monkeypatch.setattr(sys, "stderr", tty)
    assert cli.main(["render", "--style", "terminal", "--size", "320x180", "--seed", "1"]) == 0
    assert "100%" in tty.getvalue()
    assert tty.getvalue().endswith("\r")  # the line is cleared afterwards


def test_windowed_builds_without_stdout_still_render(here, monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    assert cli.main(["render", "--style", "terminal", "--size", "320x180", "--seed", "1"]) == 0
    assert (here / "wallpaper-terminal-320x180-1.png").is_file()


def test_help_exits_0(capsys):
    code, out, _ = run(capsys, "render", "--help")
    assert code == 0 and "--chip-label" in out


def test_entry_point_sends_commands_to_the_cli(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "main", lambda argv: calls.append(argv) or 0)
    monkeypatch.setattr(wallgen_main, "_gui", lambda argv: pytest.fail("opened the window"))
    assert wallgen_main.main(["wallgen", "render", "--seed", "3"]) == 0
    assert wallgen_main.main(["wallgen", "list"]) == 0
    assert wallgen_main.main(["wallgen", "--help"]) == 0
    assert calls == [["render", "--seed", "3"], ["list"], ["--help"]]


def test_the_cli_never_imports_qt():
    # A fresh interpreter: this test process has Qt loaded already.
    probe = "import sys, wallgen.__main__, wallgen.cli; print(any(m.startswith('PySide6') for m in sys.modules))"
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "False"
