import random

from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec


def test_ctx_reads_size_and_palette_from_the_spec():
    ctx = Ctx(RenderSpec(width=1920, height=1080, palette="amber", quiet_zone="right"))
    assert (ctx.W, ctx.H) == (1920, 1080)
    assert ctx.pal["primary"] == (255, 168, 64)
    assert ctx.zone == "right"
    assert ctx.portrait is False


def test_ctx_rng_is_a_private_instance_seeded_reproducibly():
    ctx_a = Ctx(RenderSpec(seed=99))
    ctx_b = Ctx(RenderSpec(seed=99))
    assert isinstance(ctx_a.rng, random.Random)
    assert [ctx_a.rng.random() for _ in range(5)] == [ctx_b.rng.random() for _ in range(5)]


def test_ctx_rng_does_not_touch_the_global_random_module():
    before = random.getstate()
    Ctx(RenderSpec(seed=123)).rng.random()
    assert random.getstate() == before


def test_quiet_and_quiet_mask_stay_in_range():
    ctx = Ctx(RenderSpec(width=640, height=360, quiet_zone="left"))
    assert 0.0 <= ctx.quiet(0, 0) <= 1.0
    assert 0.0 <= ctx.quiet(640, 360) <= 1.0
    mask = ctx.quiet_mask()
    assert mask.shape == (360, 640)
    assert mask.min() >= 0.0
