from dataclasses import fields
from typing import get_args

from wallgen.engine.spec import COMMON_FIELDS, PALETTES, SIZES, STYLE_FIELDS, RenderSpec, Style


def test_render_spec_defaults():
    spec = RenderSpec()
    assert spec.style == "pcb"
    assert (spec.width, spec.height) == (2560, 1440)
    assert spec.palette == "cyber"
    assert spec.quiet_zone == "left"
    assert spec.gutter is True
    assert spec.cursor is True


def test_at_returns_a_new_spec_with_only_size_changed():
    spec = RenderSpec(style="terminal", seed=42, palette="amber")
    resized = spec.at(3440, 1440)
    assert resized.width == 3440
    assert resized.height == 1440
    assert resized.style == "terminal"
    assert resized.seed == 42
    assert resized.palette == "amber"
    assert spec.width == 2560  # original untouched (frozen dataclass)


def test_sizes_and_palettes_cover_the_known_set():
    assert SIZES["1440p"] == (2560, 1440)
    assert SIZES["uw-1440"] == (3440, 1440)
    assert set(PALETTES) == {"cyber", "amber", "matrix", "violet", "ice", "crimson"}
    for palette in PALETTES.values():
        assert set(palette) == {
            "primary", "primary_dim", "accent", "accent_dim",
            "spark", "rare", "ok", "warn", "bg",
        }


def test_style_option_defaults_keep_todays_look():
    spec = RenderSpec()
    assert spec.blueprint_subject == "flange"
    assert spec.pcb_traces == spec.contour_lines == spec.rain_density == "normal"
    assert all(getattr(spec, name) is True for name in (
        "blueprint_grid", "blueprint_dimensions", "blueprint_labels", "pcb_hero_chip",
        "pcb_small_chips", "pcb_components", "contour_accent", "rain_foreground"))


def test_every_spec_field_is_common_or_belongs_to_exactly_one_style():
    assert set(STYLE_FIELDS) == set(get_args(Style))
    owned = [name for names in STYLE_FIELDS.values() for name in names]
    assert sorted([*COMMON_FIELDS, *owned]) == sorted(field.name for field in fields(RenderSpec))
