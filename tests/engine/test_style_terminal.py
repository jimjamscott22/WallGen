from wallgen.engine.ctx import Ctx
from wallgen.engine.spec import RenderSpec
from wallgen.engine.styles.terminal import DEFAULT_SESSION, parse_session, render_terminal


def test_parse_session_recognizes_commands_status_and_output():
    rows = parse_session("$ ls\n[ok] done\nplain text\n")
    assert rows == [("cmd", "ls"), ("status:ok", "done"), ("out", "plain text")]


def test_render_terminal_falls_back_to_default_session_when_empty():
    spec = RenderSpec(style="terminal", width=480, height=270, seed=3, session_text="")
    ctx = Ctx(spec)
    image = render_terminal(ctx, spec, lambda fraction, note: None)
    assert image.size == (480, 270)
    assert parse_session(DEFAULT_SESSION)  # sanity: default text parses to something


def test_render_terminal_uses_custom_session_text():
    spec = RenderSpec(style="terminal", width=480, height=270, seed=3,
                       session_text="$ echo hi\nhi\n", user="me@box")
    ctx = Ctx(spec)
    image = render_terminal(ctx, spec, lambda fraction, note: None)
    assert image.size == (480, 270)


def test_render_terminal_reports_monotonic_progress():
    calls = []
    spec = RenderSpec(style="terminal", width=480, height=270, seed=3)
    ctx = Ctx(spec)
    render_terminal(ctx, spec, lambda fraction, note: calls.append(fraction))
    assert len(calls) >= 3
    assert calls == sorted(calls)
