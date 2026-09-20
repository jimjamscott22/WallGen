from wallgen.engine import EngineError, PALETTES, RenderSpec, SIZES, preview, render


def test_render_dispatches_to_the_requested_style():
    spec = RenderSpec(style="pcb", width=480, height=270, seed=2)
    image = render(spec)
    assert image.size == (480, 270)


def test_render_works_without_a_progress_callback():
    spec = RenderSpec(style="terminal", width=480, height=270, seed=2)
    image = render(spec)  # progress=None, must not raise
    assert image.size == (480, 270)


def test_preview_scales_down_and_preserves_aspect_ratio():
    spec = RenderSpec(style="terminal", width=2560, height=1440, seed=3)
    image = preview(spec, max_width=640)
    assert image.size == (640, 360)


def test_preview_does_not_upscale_when_already_smaller_than_max_width():
    spec = RenderSpec(style="pcb", width=480, height=270, seed=3)
    image = preview(spec, max_width=1280)
    assert image.size == (480, 270)


def test_render_calls_progress_from_start_to_done():
    calls = []
    spec = RenderSpec(style="codeblock", width=480, height=270, seed=4)
    render(spec, progress=lambda fraction, note: calls.append(fraction))
    assert calls[0] == 0.0
    assert calls[-1] == 1.0
    assert calls == sorted(calls)


def test_public_exports_are_importable():
    assert RenderSpec().style == "pcb"
    assert "cyber" in PALETTES
    assert "1440p" in SIZES
    assert issubclass(EngineError, Exception)
