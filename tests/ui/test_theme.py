from wallgen.ui import theme


def test_color_tokens_match_approved_design():
    assert theme.BG_WINDOW == "#1B1917"
    assert theme.BG_PANEL == "#242019"
    assert theme.BG_VIEWPORT == "#08090A"
    assert theme.BG_SEED == "#16140F"
    assert theme.HAIRLINE == "#3A3229"
    assert theme.TEXT_PRIMARY == "#EDE6D8"
    assert theme.TEXT_MUTED == "#8C8272"
    assert theme.COPPER_LIGHT == "#E4A574"
    assert theme.COPPER == "#B26A3E"
    assert theme.COPPER_HOVER == "#C67A4B"
    assert theme.COPPER_DARK == "#6B3D22"
    assert theme.VERDIGRIS == "#4FA695"


def test_stylesheet_uses_the_tokens():
    css = theme.stylesheet()
    assert theme.BG_WINDOW in css
    assert theme.COPPER in css
    assert "QPushButton#generate" in css


def test_colors_dict_matches_constants():
    assert theme.COLORS["copper"] == theme.COPPER
    assert theme.COLORS["verdigris"] == theme.VERDIGRIS
