from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit

from wallgen.ui.widgets import (
    LibraryThumbnail,
    MonitorChip,
    ProgressTrack,
    RerollDial,
    SeedField,
    StatusDot,
)


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


def test_monitor_chip_exposes_name_and_active_state(qtbot):
    chip = MonitorChip("DELL U2719", "2560 x 1440", active=False)
    qtbot.addWidget(chip)
    assert chip.name_text() == "DELL U2719"
    assert chip.is_active() is False

    all_chip = MonitorChip("All", "", active=True)
    qtbot.addWidget(all_chip)
    assert all_chip.is_active() is True


def test_library_thumbnail_exposes_style_label(qtbot):
    thumb = LibraryThumbnail("PCB", "#45E0E8", "#0E1C24")
    qtbot.addWidget(thumb)
    assert thumb.style_label() == "PCB"


def test_monitor_chip_role_reflects_active_state(qtbot):
    inactive = MonitorChip("DELL U2719", "2560 x 1440", active=False)
    qtbot.addWidget(inactive)
    assert inactive.property("role") == "chip"

    active = MonitorChip("All", "", active=True)
    qtbot.addWidget(active)
    assert active.property("role") == "chip-active"


def test_monitor_chip_suppresses_empty_resolution(qtbot):
    from PySide6.QtWidgets import QLabel

    chip = MonitorChip("All", "", active=True)
    qtbot.addWidget(chip)
    value_labels = [l for l in chip.findChildren(QLabel) if l.property("role") == "value"]
    field_labels = [l for l in chip.findChildren(QLabel) if l.property("role") == "field-label"]
    assert len(value_labels) == 1  # just the name
    assert len(field_labels) == 0  # no resolution label when resolution is empty


def test_seed_field_only_accepts_digits(qtbot):
    field = SeedField(5)
    qtbot.addWidget(field)
    edit = field.findChild(QLineEdit)
    edit.clear()
    qtbot.keyClicks(edit, "12ab3")
    assert field.seed() == 123


def test_seed_field_stays_within_the_32_bit_range(qtbot):
    field = SeedField(5)
    qtbot.addWidget(field)
    edit = field.findChild(QLineEdit)
    edit.clear()
    qtbot.keyClicks(edit, "99999999999")
    assert field.seed() <= 2**31 - 1


def test_seed_field_accepts_the_max_seed_but_rejects_one_more_digit_past_it(qtbot):
    field = SeedField(5)
    qtbot.addWidget(field)
    edit = field.findChild(QLineEdit)
    edit.clear()
    qtbot.keyClicks(edit, "2147483647")
    assert field.seed() == 2**31 - 1
    edit.clear()
    qtbot.keyClicks(edit, "2147483648")  # final digit pushes it past the max, so it is rejected
    assert field.seed() == 214748364


def test_seed_field_reads_empty_as_zero(qtbot):
    field = SeedField(5)
    qtbot.addWidget(field)
    field.findChild(QLineEdit).clear()
    assert field.seed() == 0


def test_progress_track_clamps_the_fraction(qtbot):
    track = ProgressTrack()
    qtbot.addWidget(track)
    assert track.fraction() == 0.0
    track.set_fraction(0.4)
    assert track.fraction() == 0.4
    track.set_fraction(7)
    assert track.fraction() == 1.0
    track.set_fraction(-3)
    assert track.fraction() == 0.0


def test_progress_track_paints_the_fill(qtbot):
    track = ProgressTrack()
    qtbot.addWidget(track)
    track.resize(200, 3)
    idle = track.grab().toImage()
    track.set_fraction(0.5)
    partial = track.grab().toImage()
    assert partial != idle
