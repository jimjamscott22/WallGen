import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from wallgen.ui import mock_data
from wallgen.ui.style_options import STYLE_ORDER


def test_mock_monitors_have_required_shape():
    assert len(mock_data.MOCK_MONITORS) == 3
    for monitor in mock_data.MOCK_MONITORS:
        assert set(monitor) == {"name", "resolution", "active"}
    assert mock_data.MOCK_MONITORS[0]["active"] is True


def test_mock_library_items_reference_known_styles():
    assert len(mock_data.MOCK_LIBRARY) == 6
    for item in mock_data.MOCK_LIBRARY:
        assert set(item) == {"style", "dot", "art"}
        assert item["style"] in STYLE_ORDER


def test_combo_mocks_are_gone():
    for name in ("MOCK_STYLES", "MOCK_PALETTES", "MOCK_SIZES", "MOCK_QUIET_ZONES"):
        assert not hasattr(mock_data, name)
