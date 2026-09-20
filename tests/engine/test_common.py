import pytest

from wallgen.engine import common
from wallgen.engine.common import EngineError, font, has_cjk, mul


def test_mul_scales_and_clamps_channels():
    assert mul((100, 200, 250), 0.5) == (50, 100, 125)
    assert mul((100, 200, 250), 2.0) == (200, 255, 255)
    assert mul((100, 200, 250), -1.0) == (0, 0, 0)


def test_font_resolves_a_real_font():
    face = font("mono", 24)
    assert face is not None


def test_font_raises_engine_error_when_nothing_is_found(monkeypatch):
    common._resolve_fonts.cache_clear()
    monkeypatch.setitem(common.FONT_CANDIDATES, "mono", ["/no/such/font.ttf"])
    monkeypatch.setitem(common.FONT_CANDIDATES, "mono_b", [])
    monkeypatch.setitem(common.FONT_CANDIDATES, "sans_b", [])
    monkeypatch.setitem(common.FONT_CANDIDATES, "cjk", [])
    with pytest.raises(EngineError):
        font("mono", 24)
    common._resolve_fonts.cache_clear()


def test_has_cjk_returns_a_bool():
    assert isinstance(has_cjk(), bool)
