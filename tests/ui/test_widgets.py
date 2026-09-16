from PySide6.QtCore import Qt

from wallgen.ui.widgets import StatusDot, SeedField, RerollDial


def test_status_dot_color_round_trip(qtbot):
    dot = StatusDot("#4FA695")
    qtbot.addWidget(dot)
    assert dot.color() == "#4FA695"
    dot.set_color("#B26A3E")
    assert dot.color() == "#B26A3E"


def test_seed_field_round_trip(qtbot):
    field = SeedField(20260813)
    qtbot.addWidget(field)
    assert field.seed() == 20260813
    field.set_seed(42)
    assert field.seed() == 42


def test_reroll_dial_emits_rerolled_on_click(qtbot):
    dial = RerollDial()
    qtbot.addWidget(dial)
    with qtbot.waitSignal(dial.rerolled, timeout=1000):
        qtbot.mouseClick(dial, Qt.LeftButton)
