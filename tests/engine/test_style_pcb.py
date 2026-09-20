from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec
from wallgen.engine.styles.pcb import render_pcb


def test_render_pcb_returns_correctly_sized_image():
    spec = RenderSpec(style="pcb", width=480, height=270, seed=1, mark="TEST")
    ctx = Ctx(spec)
    image = render_pcb(ctx, spec, lambda fraction, note: None)
    assert image.size == (480, 270)
    assert image.mode == "RGB"


def test_render_pcb_reports_monotonic_progress():
    calls = []
    spec = RenderSpec(style="pcb", width=480, height=270, seed=1)
    ctx = Ctx(spec)
    render_pcb(ctx, spec, lambda fraction, note: calls.append(fraction))
    assert len(calls) >= 3
    assert calls == sorted(calls)
    assert all(0.0 <= f <= 1.0 for f in calls)
