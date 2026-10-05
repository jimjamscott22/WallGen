from typing import get_args

import pytest
from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QPlainTextEdit

from wallgen.engine import RenderSpec
from wallgen.engine.spec import Style
from wallgen.ui.style_options import (
    FIELDS_BY_STYLE,
    STYLE_LABELS,
    STYLE_ORDER,
    StyleOptionsPanel,
)

SPEC_KEYS = {
    "mark", "submark", "chip_label",
    "glyphs",
    "user", "title", "session_text",
    "code_text", "caption", "gutter", "cursor",
}


def test_style_order_and_labels_cover_all_four_styles():
    assert STYLE_ORDER == ["pcb", "coderain", "terminal", "codeblock"]
    assert STYLE_LABELS == {
        "pcb": "PCB",
        "coderain": "Code rain",
        "terminal": "Terminal",
        "codeblock": "Code block",
    }


def test_style_order_matches_the_engine_style_set():
    assert set(STYLE_ORDER) == set(get_args(Style))
    assert set(FIELDS_BY_STYLE) == set(STYLE_ORDER)


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


def test_values_cover_every_spec_field_and_build_the_default_spec(qtbot):
    panel = StyleOptionsPanel()
    qtbot.addWidget(panel)
    values = panel.values()
    assert set(values) == SPEC_KEYS
    assert RenderSpec(**values) == RenderSpec()


def test_editor_kinds(qtbot):
    panel = StyleOptionsPanel()
    qtbot.addWidget(panel)
    assert isinstance(panel.editor("mark"), QLineEdit)
    assert isinstance(panel.editor("glyphs"), QComboBox)
    assert isinstance(panel.editor("session_text"), QPlainTextEdit)
    assert isinstance(panel.editor("gutter"), QCheckBox)


def test_edits_flow_into_values(qtbot):
    panel = StyleOptionsPanel()
    qtbot.addWidget(panel)
    panel.editor("mark").setText("J A M I E")
    panel.editor("glyphs").setCurrentText("ascii")
    panel.editor("code_text").setPlainText("print('hi')")
    panel.editor("gutter").setChecked(False)
    values = panel.values()
    assert values["mark"] == "J A M I E"
    assert values["glyphs"] == "ascii"
    assert values["code_text"] == "print('hi')"
    assert values["gutter"] is False


def test_emptied_user_field_falls_back_to_the_engine_default(qtbot):
    panel = StyleOptionsPanel()
    qtbot.addWidget(panel)
    panel.editor("user").setText("jamie@box")
    assert panel.values()["user"] == "jamie@box"
    panel.editor("user").setText("")
    assert panel.values()["user"] == RenderSpec().user


def test_edits_survive_switching_styles(qtbot):
    panel = StyleOptionsPanel()
    qtbot.addWidget(panel)
    panel.editor("mark").setText("HELLO")
    panel.editor("session_text").setPlainText("$ ls")
    panel.set_style("terminal")
    panel.set_style("pcb")
    values = panel.values()
    assert values["mark"] == "HELLO"
    assert values["session_text"] == "$ ls"
