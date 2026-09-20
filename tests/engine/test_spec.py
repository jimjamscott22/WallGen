from wallgen.engine.spec import PALETTES, SIZES, RenderSpec


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
