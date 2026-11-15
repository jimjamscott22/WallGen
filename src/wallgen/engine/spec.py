from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from wallgen.engine.common import C

Style = Literal["pcb", "coderain", "terminal", "codeblock", "blueprint", "contour"]
QuietZone = Literal["left", "right", "top", "bottom", "none"]
BlueprintLayout = Literal["centered", "offset"]
ContourLayout = Literal["ridge", "island"]
BlueprintSubject = Literal["flange", "gear", "bearing", "bracket"]
TraceDensity = Literal["sparse", "normal", "dense"]
ContourLines = Literal["few", "normal", "many"]
RainDensity = Literal["light", "normal", "heavy"]

SIZES: dict[str, tuple[int, int]] = {
    # 16:9
    "1080p": (1920, 1080), "1440p": (2560, 1440), "4k": (3840, 2160),
    # 16:10
    "wxga+": (1920, 1200), "wqxga": (2560, 1600), "4k-16x10": (3840, 2400),
    # ultrawide / super-ultrawide
    "uw-1080": (2560, 1080), "uw-1440": (3440, 1440), "uw-4k": (5120, 2160),
    "suw-1440": (5120, 1440),
    # 3:2, 4:3
    "surface": (2256, 1504), "ipad": (2048, 1536),
    # portrait / mobile
    "phone": (1179, 2556), "phone-qhd": (1440, 3200), "ipad-portrait": (1536, 2048),
    "portrait-1440": (1440, 2560),
}

PALETTES: dict[str, dict[str, tuple[int, ...]]] = {
    "cyber":  dict(primary=C(34, 226, 255),  primary_dim=C(16, 132, 165),
                   accent=C(255, 47, 200),   accent_dim=C(158, 24, 118),
                   spark=C(150, 90, 255),    rare=C(255, 170, 60),
                   ok=C(80, 240, 150),       warn=C(255, 190, 90),
                   bg=C(4, 6, 10)),
    "amber":  dict(primary=C(255, 168, 64),  primary_dim=C(150, 92, 26),
                   accent=C(255, 92, 40),    accent_dim=C(140, 44, 18),
                   spark=C(255, 214, 130),   rare=C(120, 220, 255),
                   ok=C(180, 240, 120),      warn=C(255, 120, 60),
                   bg=C(14, 8, 4)),
    "matrix": dict(primary=C(60, 255, 130),  primary_dim=C(26, 150, 78),
                   accent=C(150, 255, 190),  accent_dim=C(40, 120, 70),
                   spark=C(220, 255, 230),   rare=C(120, 255, 200),
                   ok=C(80, 240, 150),       warn=C(230, 255, 120),
                   bg=C(3, 8, 5)),
    "violet": dict(primary=C(168, 120, 255), primary_dim=C(88, 58, 158),
                   accent=C(255, 110, 220),  accent_dim=C(140, 40, 116),
                   spark=C(120, 220, 255),   rare=C(255, 200, 120),
                   ok=C(130, 240, 200),      warn=C(255, 190, 120),
                   bg=C(8, 5, 16)),
    "ice":    dict(primary=C(150, 220, 255), primary_dim=C(64, 116, 158),
                   accent=C(90, 255, 235),   accent_dim=C(30, 130, 120),
                   spark=C(230, 245, 255),   rare=C(160, 180, 255),
                   ok=C(120, 240, 200),      warn=C(255, 210, 140),
                   bg=C(4, 8, 14)),
    "crimson":dict(primary=C(255, 90, 90),   primary_dim=C(150, 40, 44),
                   accent=C(255, 170, 60),   accent_dim=C(140, 82, 20),
                   spark=C(255, 220, 200),   rare=C(120, 200, 255),
                   ok=C(255, 150, 90),       warn=C(255, 220, 120),
                   bg=C(14, 4, 6)),
}


@dataclass(frozen=True, slots=True)
class RenderSpec:
    style: Style = "pcb"
    width: int = 2560
    height: int = 1440
    palette: str = "cyber"
    seed: int = 0
    quiet_zone: QuietZone = "left"
    mark: str = ""
    submark: str = ""
    chip_label: str = ""
    user: str = "you@localhost"
    title: str = ""
    session_text: str = ""
    code_text: str = ""
    caption: str = ""
    glyphs: Literal["mixed", "ascii"] = "mixed"
    gutter: bool = True
    cursor: bool = True
    blueprint_layout: BlueprintLayout = "centered"
    contour_layout: ContourLayout = "ridge"
    # Style options: every default reproduces the look from before they existed.
    blueprint_subject: BlueprintSubject = "flange"
    blueprint_grid: bool = True
    blueprint_dimensions: bool = True
    blueprint_labels: bool = True
    pcb_hero_chip: bool = True
    pcb_small_chips: bool = True
    pcb_traces: TraceDensity = "normal"
    pcb_components: bool = True
    contour_lines: ContourLines = "normal"
    contour_accent: bool = True
    rain_density: RainDensity = "normal"
    rain_foreground: bool = True

    def at(self, w: int, h: int) -> "RenderSpec":
        return replace(self, width=w, height=h)


# Which settings shape which wallpaper. Every RenderSpec field is either common
# to all styles or owned by exactly one; a spec still carries the other styles'
# fields (the panel keeps them across style switches), but they do not affect
# the image. The options panel and the library search both follow this map.
COMMON_FIELDS: tuple[str, ...] = ("style", "width", "height", "palette", "seed", "quiet_zone")
STYLE_FIELDS: dict[str, tuple[str, ...]] = {
    "pcb": ("mark", "submark", "chip_label", "pcb_hero_chip", "pcb_small_chips",
            "pcb_traces", "pcb_components"),
    "coderain": ("glyphs", "rain_density", "rain_foreground"),
    "terminal": ("user", "title", "session_text"),
    "codeblock": ("code_text", "caption", "gutter", "cursor"),
    "blueprint": ("blueprint_layout", "blueprint_subject", "blueprint_grid",
                  "blueprint_dimensions", "blueprint_labels"),
    "contour": ("contour_layout", "contour_lines", "contour_accent"),
}
