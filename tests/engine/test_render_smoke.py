import pytest

from wallgen.engine import RenderSpec, preview, render

STYLES = ["pcb", "coderain", "terminal", "codeblock"]


@pytest.mark.parametrize("style", STYLES)
def test_render_produces_an_image_of_the_requested_size(style):
    spec = RenderSpec(style=style, width=480, height=270, seed=11)
    image = render(spec)
    assert image.size == (480, 270)
    assert image.mode == "RGB"


@pytest.mark.parametrize("style", STYLES)
def test_preview_is_never_wider_than_max_width(style):
    spec = RenderSpec(style=style, width=2560, height=1440, seed=12)
    image = preview(spec, max_width=640)
    assert image.width <= 640


@pytest.mark.parametrize("style", STYLES)
def test_same_seed_and_spec_produce_identical_bytes(style):
    spec = RenderSpec(style=style, width=480, height=270, seed=13)
    assert render(spec).tobytes() == render(spec).tobytes()
