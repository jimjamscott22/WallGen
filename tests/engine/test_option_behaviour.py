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


@pytest.mark.parametrize("option", [dict(pcb_hero_chip=False), dict(pcb_small_chips=False),
                                    dict(pcb_traces="sparse"), dict(pcb_traces="dense"),
                                    dict(pcb_components=False)])
def test_each_pcb_option_changes_the_image(option):
    assert (image(style="pcb") != image(style="pcb", **option)).any()


def test_trace_density_orders_the_amount_of_light():
    sparse, normal, dense = (image(style="pcb", pcb_traces=value).mean()
                             for value in ("sparse", "normal", "dense"))
    assert sparse < normal < dense


def test_removing_components_leaves_the_traces_in_place():
    default, off = image(style="pcb"), image(style="pcb", pcb_components=False)
    assert (off - default).max() <= 24  # nothing new appears: no trace moved
    assert (default - off).max() >= 40  # something bright was removed


def test_hero_chip_off_ignores_its_label_and_keeps_the_wordmark():
    marked = dict(style="pcb", pcb_hero_chip=False, mark="WALLGEN", chip_label="WG-1")
    assert (image(**marked) == image(**{**marked, "chip_label": ""})).all()
    assert (image(**marked) != image(**{**marked, "mark": ""})).any()


def test_pcb_with_everything_off_is_not_blank():
    bare = image(style="pcb", pcb_hero_chip=False, pcb_small_chips=False,
                 pcb_traces="sparse", pcb_components=False)
    assert bare.max() > 120


@pytest.mark.parametrize("layout", ["ridge", "island"])
@pytest.mark.parametrize("option", [dict(contour_lines="few"), dict(contour_lines="many"),
                                    dict(contour_accent=False)])
def test_each_contour_option_changes_the_image(layout, option):
    base = dict(style="contour", contour_layout=layout)
    assert (image(**base) != image(**base, **option)).any()


@pytest.mark.parametrize("layout", ["ridge", "island"])
def test_line_count_orders_the_amount_of_light(layout):
    few, normal, many = (image(style="contour", contour_layout=layout, contour_lines=value).mean()
                         for value in ("few", "normal", "many"))
    assert few < normal < many


@pytest.mark.parametrize("option", [dict(rain_density="light"), dict(rain_density="heavy"),
                                    dict(rain_foreground=False)])
def test_each_rain_option_changes_the_image(option):
    assert (image(style="coderain") != image(style="coderain", **option)).any()


def test_rain_density_orders_the_amount_of_light():
    light, normal, heavy = (image(style="coderain", rain_density=value).mean()
                            for value in ("light", "normal", "heavy"))
    assert light < normal < heavy


def test_removing_foreground_streaks_leaves_the_rest_in_place():
    default, off = image(style="coderain"), image(style="coderain", rain_foreground=False)
    assert (off - default).max() <= 1
    assert (default - off).max() >= 10
