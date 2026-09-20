from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec
from wallgen.engine.styles.coderain import render_coderain


def test_render_coderain_returns_correctly_sized_image():
    spec = RenderSpec(style="coderain", width=480, height=270, seed=2)
    ctx = Ctx(spec)
    image = render_coderain(ctx, spec, lambda fraction, note: None)
    assert image.size == (480, 270)
    assert image.mode == "RGB"


def test_render_coderain_respects_ascii_only_glyphs():
    spec = RenderSpec(style="coderain", width=480, height=270, seed=2, glyphs="ascii")
    ctx = Ctx(spec)
    image = render_coderain(ctx, spec, lambda fraction, note: None)
    assert image.size == (480, 270)


def test_render_coderain_reports_monotonic_progress():
    calls = []
    spec = RenderSpec(style="coderain", width=480, height=270, seed=2)
    ctx = Ctx(spec)
    render_coderain(ctx, spec, lambda fraction, note: calls.append(fraction))
    assert len(calls) >= 3
    assert calls == sorted(calls)
