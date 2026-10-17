from PIL import Image

from wallgen import selftest
from wallgen.resources import ICON_PATH


def test_the_icon_ships_in_every_size_windows_uses():
    with Image.open(ICON_PATH) as icon:
        sizes = icon.info["sizes"]
    assert {(16, 16), (24, 24), (32, 32), (48, 48), (256, 256)} <= sizes


def test_self_test_passes_and_writes_its_report(qtbot, tmp_path, capsys):
    assert selftest.run() == 0
    report = (tmp_path / "appdata" / "WallGen" / "self-test.log").read_text(encoding="utf-8")
    assert report.endswith("PASSED\n")
    for name in ("data folder", "app icon", "render pcb", "render codeblock", "main window"):
        assert f"ok    {name}:" in report
    assert capsys.readouterr().out == report


def test_a_failing_check_fails_the_run_and_the_rest_still_run(qtbot, tmp_path, monkeypatch):
    def broken(spec, progress=None):
        raise OSError("font file missing from the bundle")

    monkeypatch.setattr(selftest, "render", broken)
    assert selftest.run() == 1
    report = (tmp_path / "appdata" / "WallGen" / "self-test.log").read_text(encoding="utf-8")
    assert "FAIL  render pcb:" in report and "font file missing from the bundle" in report
    assert "ok    main window:" in report
    assert report.endswith("FAILED\n")


def test_windowed_builds_have_no_stdout(qtbot, monkeypatch):
    monkeypatch.setattr(selftest.sys, "stdout", None)
    assert selftest.run() == 0
