"""Engine behaviour of the per-style options (Blueprint subjects, switches, amounts)."""
import numpy as np
import pytest

from wallgen.engine import RenderSpec, render
from wallgen.engine.styles.blueprint_subjects import SUBJECTS


def image(**kwargs):
    kwargs = {"width": 960, "height": 540, "seed": 7, **kwargs}  # large enough for lettering
    return np.asarray(render(RenderSpec(**kwargs)), np.int16)


@pytest.mark.parametrize("switch", ["blueprint_grid", "blueprint_dimensions", "blueprint_labels"])
def test_each_blueprint_switch_changes_the_image(switch):
    assert (image(style="blueprint") != image(style="blueprint", **{switch: False})).any()


def test_blueprint_with_every_switch_off_still_draws_the_subject():
    bare = dict(style="blueprint", blueprint_grid=False, blueprint_dimensions=False,
                blueprint_labels=False)
    assert (image(**bare) != image(**{**bare, "seed": 8})).any()  # seeded geometry is there
    assert image(**bare).max() > 120  # main-weight linework is visible


def test_flange_is_registered_with_its_title():
    assert SUBJECTS["flange"][1] == "FLANGE ASSEMBLY"
