from dataclasses import replace
from typing import get_args

import pytest

from wallgen.engine import RenderSpec, preview, render
from wallgen.engine.spec import Style

STYLES = get_args(Style)


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


@pytest.mark.parametrize("style, layouts", [
    ("blueprint", {"blueprint_layout": "offset"}),
    ("contour", {"contour_layout": "island"}),
])
def test_alternate_layout_is_seeded_and_preserved_in_preview(style, layouts):
    spec = RenderSpec(style=style, width=800, height=1200, seed=7, **layouts)
    reduced = spec.at(320, 480)
    actual = preview(spec, max_width=320).tobytes()
    assert actual == render(reduced).tobytes() == render(reduced).tobytes()
    assert actual != render(replace(reduced, seed=8)).tobytes()
