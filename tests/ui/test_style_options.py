import pytest

from wallgen.ui.style_options import STYLE_LABELS, STYLE_ORDER, StyleOptionsPanel


def test_style_order_and_labels_cover_all_four_styles():
    assert STYLE_ORDER == ["pcb", "coderain", "terminal", "codeblock"]
    assert STYLE_LABELS == {
        "pcb": "PCB",
        "coderain": "Code rain",
        "terminal": "Terminal",
        "codeblock": "Code block",
    }


def test_panel_defaults_to_pcb(qtbot):
    panel = StyleOptionsPanel()
    qtbot.addWidget(panel)
    assert panel.current_style_label() == "PCB options"


@pytest.mark.parametrize("style", STYLE_ORDER)
def test_set_style_switches_the_title(qtbot, style):
    panel = StyleOptionsPanel()
    qtbot.addWidget(panel)
    panel.set_style(style)
    assert panel.current_style_label() == f"{STYLE_LABELS[style]} options"


def test_set_style_rejects_unknown_style(qtbot):
    panel = StyleOptionsPanel()
    qtbot.addWidget(panel)
    with pytest.raises(ValueError):
        panel.set_style("not-a-style")
