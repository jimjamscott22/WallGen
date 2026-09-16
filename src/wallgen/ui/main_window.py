from __future__ import annotations

import random

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from wallgen.ui import theme
from wallgen.ui.mock_data import (
    MOCK_LIBRARY,
    MOCK_MONITORS,
    MOCK_PALETTES,
    MOCK_QUIET_ZONES,
    MOCK_SIZES,
    MOCK_STYLES,
)
from wallgen.ui.style_options import STYLE_LABELS, StyleOptionsPanel
from wallgen.ui.widgets import LibraryThumbnail, MonitorChip, RerollDial, SeedField, StatusDot


def _labeled_field(label_text: str, value_widget: QWidget) -> QWidget:
    wrapper = QWidget()
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    label = QLabel(label_text)
    label.setProperty("role", "field-label")
    layout.addWidget(label)
    layout.addWidget(value_widget)
    return wrapper


def _hairline(vertical: bool = False) -> QFrame:
    line = QFrame()
    line.setProperty("role", "hairline")
    if vertical:
        line.setFixedWidth(1)
        line.setFixedHeight(30)
    else:
        line.setFixedHeight(1)
    return line


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("WallGen")
        self.resize(1440, 900)
        self.setStyleSheet(theme.stylesheet())

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_header())
        root_layout.addWidget(_hairline())
        root_layout.addWidget(self._build_control_rail())
        root_layout.addWidget(_hairline())
        root_layout.addWidget(self._build_main_area(), 1)
        root_layout.addWidget(_hairline())
        root_layout.addWidget(self._build_set_on_row())
        root_layout.addWidget(_hairline())
        root_layout.addWidget(self._build_library_row())

    def _build_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(28, 16, 28, 16)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        brand.addWidget(StatusDot(theme.VERDIGRIS, glow=True))
        title = QLabel("WallGen")
        title.setStyleSheet(f"font-size: 19px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        brand.addWidget(title)
        subtitle = QLabel("wallpaper generator")
        subtitle.setProperty("role", "field-label")
        brand.addWidget(subtitle)
        layout.addLayout(brand)
        layout.addStretch(1)

        version = QLabel("v0.1")
        version.setProperty("role", "field-label")
        layout.addWidget(version)
        return header

    def _build_control_rail(self) -> QWidget:
        rail = QWidget()
        layout = QHBoxLayout(rail)
        layout.setContentsMargins(28, 14, 28, 14)
        layout.setSpacing(20)

        self.style_combo = QComboBox()
        self.style_combo.addItems([STYLE_LABELS[s] for s in MOCK_STYLES])
        layout.addWidget(_labeled_field("Style", self.style_combo))
        layout.addWidget(_hairline(vertical=True))

        self.palette_combo = QComboBox()
        self.palette_combo.addItems([p.capitalize() for p in MOCK_PALETTES])
        layout.addWidget(_labeled_field("Palette", self.palette_combo))
        layout.addWidget(_hairline(vertical=True))

        self.size_combo = QComboBox()
        self.size_combo.addItems(MOCK_SIZES)
        layout.addWidget(_labeled_field("Size", self.size_combo))
        layout.addWidget(_hairline(vertical=True))

        self.quiet_combo = QComboBox()
        self.quiet_combo.addItems([q.capitalize() for q in MOCK_QUIET_ZONES])
        layout.addWidget(_labeled_field("Quiet zone", self.quiet_combo))

        layout.addStretch(1)

        self.seed_field = SeedField(20260813)
        layout.addWidget(_labeled_field("Seed", self.seed_field))

        self.reroll_dial = RerollDial()
        self.reroll_dial.rerolled.connect(self._on_reroll)
        layout.addWidget(self.reroll_dial)

        self.generate_button = QPushButton("Generate")
        self.generate_button.setObjectName("generate")
        self.generate_button.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.generate_button)

        self.style_combo.currentIndexChanged.connect(self._on_style_changed)
        return rail

    def _build_main_area(self) -> QWidget:
        area = QWidget()
        layout = QHBoxLayout(area)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(20)

        preview_column = QVBoxLayout()
        preview_column.setSpacing(10)

        self.viewport = QFrame()
        self.viewport.setProperty("role", "viewport")
        self.viewport.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_column.addWidget(self.viewport, 1)

        progress_track = QFrame()
        progress_track.setFixedHeight(3)
        progress_track.setStyleSheet(f"background: {theme.HAIRLINE}; border-radius: 2px;")
        preview_column.addWidget(progress_track)

        preview_widget = QWidget()
        preview_widget.setLayout(preview_column)
        layout.addWidget(preview_widget, 1)

        self.style_panel = StyleOptionsPanel()
        layout.addWidget(self.style_panel)
        return area

    def _build_set_on_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(28, 14, 28, 14)
        layout.setSpacing(14)

        label = QLabel("Set on")
        label.setProperty("role", "field-label")
        layout.addWidget(label)

        self.monitor_chips: list[MonitorChip] = []
        for monitor in MOCK_MONITORS:
            chip = MonitorChip(monitor["name"], monitor["resolution"], monitor["active"])
            self.monitor_chips.append(chip)
            layout.addWidget(chip)

        layout.addStretch(1)
        return row

    def _build_library_row(self) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(28, 14, 28, 18)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Library")
        title.setProperty("role", "field-label")
        header.addWidget(title)
        header.addStretch(1)
        layout.addLayout(header)

        strip = QHBoxLayout()
        strip.setSpacing(12)
        self.library_thumbnails: list[LibraryThumbnail] = []
        for item in MOCK_LIBRARY:
            thumb = LibraryThumbnail(STYLE_LABELS[item["style"]], item["dot"], item["art"])
            self.library_thumbnails.append(thumb)
            strip.addWidget(thumb)
        strip.addStretch(1)
        layout.addLayout(strip)
        return row

    def _on_style_changed(self, index: int) -> None:
        self.style_panel.set_style(MOCK_STYLES[index])

    def _on_reroll(self) -> None:
        self.seed_field.set_seed(random.randint(0, 99_999_999))
