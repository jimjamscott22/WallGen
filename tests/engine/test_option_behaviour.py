"""Engine behaviour of the per-style options (Blueprint subjects, switches, amounts)."""
import itertools
from typing import get_args

import numpy as np
import pytest

from wallgen.engine import RenderSpec, render
from wallgen.engine.spec import BlueprintSubject, QuietZone
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


SUBJECT_NAMES = get_args(BlueprintSubject)


def test_registry_matches_the_spec_choices():
    assert tuple(SUBJECTS) == SUBJECT_NAMES


def test_subjects_are_distinct_and_seeded():
    images = {name: image(style="blueprint", blueprint_subject=name) for name in SUBJECT_NAMES}
    for a, b in itertools.combinations(SUBJECT_NAMES, 2):
        assert (images[a] != images[b]).any()
    for name in SUBJECT_NAMES:
        assert (images[name] != image(style="blueprint", blueprint_subject=name, seed=8)).any()


@pytest.mark.parametrize("subject", SUBJECT_NAMES)
@pytest.mark.parametrize("size", [(295, 640), (860, 360), (96, 54)])  # portrait, ultrawide, tiny
@pytest.mark.parametrize("layout", ["centered", "offset"])
def test_subjects_render_at_awkward_sizes(subject, size, layout):
    for zone in get_args(QuietZone):
        spec = RenderSpec(style="blueprint", width=size[0], height=size[1], seed=3,
                          quiet_zone=zone, blueprint_subject=subject, blueprint_layout=layout)
        assert render(spec).size == size


@pytest.mark.parametrize("subject", SUBJECT_NAMES)
def test_subject_dimensions_switch_changes_the_image(subject):
    on = image(style="blueprint", blueprint_subject=subject)
    off = image(style="blueprint", blueprint_subject=subject, blueprint_dimensions=False)
    assert (on != off).any()
