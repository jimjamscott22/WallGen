import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from wallgen.ui import mock_data
from wallgen.ui.style_options import STYLE_ORDER


def test_monitor_mocks_are_gone():
    # Real detection lives in wallgen.platform_win.monitors now.
    assert not hasattr(mock_data, "MOCK_MONITORS")


def test_mock_library_items_reference_known_styles():
    assert len(mock_data.MOCK_LIBRARY) == 6
    for item in mock_data.MOCK_LIBRARY:
        assert set(item) == {"style", "dot", "art"}
        assert item["style"] in STYLE_ORDER


def test_combo_mocks_are_gone():
    for name in ("MOCK_STYLES", "MOCK_PALETTES", "MOCK_SIZES", "MOCK_QUIET_ZONES"):
        assert not hasattr(mock_data, name)
