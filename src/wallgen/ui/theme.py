"""Design tokens and QSS for WallGen's instrument-panel theme.

Chrome stays muted (charcoal + copper); saturated color is reserved for
the generated wallpaper preview itself. See the approved design canvas
for the full rationale.
"""

BG_WINDOW = "#1B1917"
BG_PANEL = "#242019"
BG_VIEWPORT = "#08090A"
BG_SEED = "#16140F"

HAIRLINE = "#3A3229"

TEXT_PRIMARY = "#EDE6D8"
TEXT_MUTED = "#8C8272"

COPPER_LIGHT = "#E4A574"
COPPER = "#B26A3E"
COPPER_HOVER = "#C67A4B"
COPPER_DARK = "#6B3D22"

VERDIGRIS = "#4FA695"

FONT_UI = "'Archivo Narrow', 'Arial Narrow', sans-serif"
FONT_MONO = "'JetBrains Mono', 'Consolas', monospace"

COLORS = {
    "bg_window": BG_WINDOW,
    "bg_panel": BG_PANEL,
    "bg_viewport": BG_VIEWPORT,
    "bg_seed": BG_SEED,
    "hairline": HAIRLINE,
    "text_primary": TEXT_PRIMARY,
    "text_muted": TEXT_MUTED,
    "copper_light": COPPER_LIGHT,
    "copper": COPPER,
    "copper_hover": COPPER_HOVER,
    "copper_dark": COPPER_DARK,
    "verdigris": VERDIGRIS,
}


def stylesheet() -> str:
    return f"""
    QMainWindow, QWidget#root {{
        background: {BG_WINDOW};
        color: {TEXT_PRIMARY};
        font-family: {FONT_UI};
    }}
    QLabel {{
        color: {TEXT_PRIMARY};
        background: transparent;
        font-family: {FONT_UI};
    }}
    QLabel[role="field-label"] {{
        color: {TEXT_MUTED};
        font-size: 11px;
    }}
    QLabel[role="value"] {{
        color: {TEXT_PRIMARY};
        font-family: {FONT_MONO};
        font-size: 14px;
    }}
    QFrame[role="hairline"] {{
        background: {HAIRLINE};
        max-height: 1px;
        min-height: 1px;
        border: none;
    }}
    QFrame[role="panel"] {{
        background: {BG_PANEL};
        border: 1px solid {HAIRLINE};
        border-radius: 4px;
    }}
    QFrame[role="viewport"] {{
        background: {BG_VIEWPORT};
        border: 1px solid {HAIRLINE};
        border-radius: 4px;
    }}
    QFrame[role="chip"] {{
        background: transparent;
        border: 1px solid {HAIRLINE};
        border-radius: 3px;
    }}
    QFrame[role="chip-active"] {{
        background: transparent;
        border: 1px solid {COPPER};
        border-radius: 3px;
    }}
    QFrame[role="sprocket"] {{
        background: {HAIRLINE};
        border: none;
    }}
    QComboBox {{
        background: transparent;
        color: {TEXT_PRIMARY};
        font-family: {FONT_UI};
        font-weight: 600;
        font-size: 14px;
        border: none;
        padding: 2px 0;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 16px;
    }}
    QPushButton#generate {{
        background: {COPPER};
        color: {BG_WINDOW};
        font-family: {FONT_UI};
        font-weight: 700;
        font-size: 14px;
        border: none;
        border-radius: 3px;
        padding: 10px 22px;
    }}
    QPushButton#generate:hover {{
        background: {COPPER_HOVER};
    }}
    """
