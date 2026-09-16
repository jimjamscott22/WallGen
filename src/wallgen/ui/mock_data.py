"""Placeholder content standing in for the render engine, the SQLite
library, and Windows monitor detection until those subsystems exist
(spec §3, §4, §5)."""

MOCK_STYLES = ["pcb", "coderain", "terminal", "codeblock"]

MOCK_PALETTES = ["cyber", "amber", "matrix", "violet", "ice", "crimson"]

MOCK_SIZES = ["2560 x 1440", "3440 x 1440", "1920 x 1080"]

MOCK_QUIET_ZONES = ["left", "top", "none"]

MOCK_MONITORS = [
    {"name": "All", "resolution": "", "active": True},
    {"name": "DELL U2719", "resolution": "2560 x 1440", "active": False},
    {"name": "LG 24MK", "resolution": "1920 x 1080", "active": False},
]

MOCK_LIBRARY = [
    {"style": "pcb", "dot": "#45E0E8", "art": "#0E1C24"},
    {"style": "coderain", "dot": "#55B378", "art": "#03110A"},
    {"style": "terminal", "dot": "#4FA695", "art": "#050807"},
    {"style": "codeblock", "dot": "#E14FA8", "art": "#08090A"},
    {"style": "pcb", "dot": "#E0A64F", "art": "#241608"},
    {"style": "pcb", "dot": "#E05070", "art": "#240810"},
]
