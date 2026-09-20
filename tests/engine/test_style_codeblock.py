from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec
from wallgen.engine.styles.codeblock import DEFAULT_CODE, render_codeblock


def test_render_codeblock_falls_back_to_default_code_when_empty():
    spec = RenderSpec(style="codeblock", width=480, height=270, seed=4, code_text="")
    ctx = Ctx(spec)
    image = render_codeblock(ctx, spec, lambda fraction, note: None)
    assert image.size == (480, 270)
    assert DEFAULT_CODE.strip()


def test_render_codeblock_uses_custom_code_text():
    spec = RenderSpec(style="codeblock", width=480, height=270, seed=4,
                       code_text="def f(x):\n    return x + 1\n", caption="a note")
    ctx = Ctx(spec)
    image = render_codeblock(ctx, spec, lambda fraction, note: None)
    assert image.size == (480, 270)


def test_render_codeblock_reports_monotonic_progress():
    calls = []
    spec = RenderSpec(style="codeblock", width=480, height=270, seed=4)
    ctx = Ctx(spec)
    render_codeblock(ctx, spec, lambda fraction, note: calls.append(fraction))
    assert len(calls) >= 3
    assert calls == sorted(calls)
