from wallgen.ui import mock_data


def test_mock_styles_cover_all_four_renderers():
    assert mock_data.MOCK_STYLES == ["pcb", "coderain", "terminal", "codeblock"]


def test_mock_monitors_have_required_shape():
    assert len(mock_data.MOCK_MONITORS) == 3
    for monitor in mock_data.MOCK_MONITORS:
        assert set(monitor) == {"name", "resolution", "active"}
    assert mock_data.MOCK_MONITORS[0]["active"] is True


def test_mock_library_items_reference_known_styles():
    assert len(mock_data.MOCK_LIBRARY) == 6
    for item in mock_data.MOCK_LIBRARY:
        assert set(item) == {"style", "dot", "art"}
        assert item["style"] in mock_data.MOCK_STYLES
