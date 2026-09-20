from concurrent.futures import ThreadPoolExecutor

from wallgen.engine import RenderSpec, render


def test_render_is_deterministic_under_concurrency():
    spec = RenderSpec(style="pcb", width=640, height=360, seed=7)
    once = render(spec).tobytes()
    with ThreadPoolExecutor(4) as ex:
        results = [f.result().tobytes() for f in
                   [ex.submit(render, spec) for _ in range(4)]]
    assert all(r == once for r in results)
