"""The WallGen main window.

Generate, the reroll dial, the preview pane, the progress track and the style
options are live: they build a RenderSpec and render a preview off-thread via
RenderController. Full renders are saved and can be set on all monitors,
or on one detected monitor (re-rendered at its native size when needed).
The library restores saved images and their full generation settings.
"""

from __future__ import annotations

import random
from pathlib import Path
import sqlite3
from typing import get_args

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wallgen.engine import PALETTES, SIZES, RenderSpec
from wallgen.engine.spec import QuietZone
from wallgen.platform_win.desktop import set_on_all_monitors, set_on_monitor
from wallgen.platform_win.monitors import Monitor, ScreenGeometry, detect_monitors
from wallgen.store.db import LibraryStore
from wallgen.ui import theme
from wallgen.ui.jobs import DEFAULT_PREVIEW_WIDTH, RenderController
from wallgen.ui.library_panel import LibraryPanel
from wallgen.ui.preview_pane import PreviewPane
from wallgen.ui.style_options import STYLE_LABELS, STYLE_ORDER, StyleOptionsPanel
from wallgen.ui.widgets import (
    MonitorChip,
    ProgressTrack,
    RerollDial,
    SeedField,
    StatusDot,
)

QUIET_ZONES = get_args(QuietZone)
DEFAULT_SIZE_KEY = "1440p"
DEFAULT_SEED = 20260813
# Marks size-combo entries that come from detected monitors, so a refresh can
# replace them without touching the presets or a loaded custom size.
MONITOR_ITEM_ROLE = Qt.UserRole + 1
# Windows sends several screen-change events while a display settles.
MONITOR_REFRESH_DELAY_MS = 750


def _screen_geometries() -> list[ScreenGeometry]:
    """Qt's view of the screens, as plain data for monitor matching."""
    result = []
    for screen in QGuiApplication.screens():
        geometry = screen.geometry()
        name = screen.name()
        # "\\.\DISPLAY1" is an adapter port, not a name worth showing.
        label = screen.model().strip() or ("" if name.startswith("\\\\.\\") else name)
        result.append(ScreenGeometry(
            label, geometry.x(), geometry.y(), geometry.width(), geometry.height(),
            screen.devicePixelRatio(),
        ))
    return result


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
    if vertical:
        # Vertical dividers get their own role: the "hairline" QSS rule
        # clamps max-height/min-height to 1px, which would collapse a
        # vertical divider's setFixedHeight(30) into an invisible dot.
        line.setProperty("role", "hairline-v")
        line.setFixedWidth(1)
        line.setFixedHeight(30)
    else:
        line.setProperty("role", "hairline")
        line.setFixedHeight(1)
    return line


class MainWindow(QMainWindow):
    def __init__(
        self, preview_max_width: int = DEFAULT_PREVIEW_WIDTH,
        render_directory: Path | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("WallGen")
        self.resize(1440, 900)
        self.setStyleSheet(theme.stylesheet())

        self.library = LibraryStore(render_directory)
        self.controller = RenderController(max_width=preview_max_width, parent=self, library=self.library)
        # The displayed full-resolution render, which the Set buttons apply.
        self._render_path: Path | None = None
        self._render_size: tuple[int, int] | None = None
        self._render_spec: RenderSpec | None = None
        # The spec of the newest submitted render or load.
        self._requested_spec: RenderSpec | None = None
        # A monitor waiting for a render at its size, set once that lands.
        self._pending_monitor: Monitor | None = None
        self._loading_id: str | None = None
        self.monitors: list[Monitor] = []
        self.monitor_chips: list[MonitorChip] = []

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

        self._connect_controller()
        self._watch_screens()
        self.refresh_monitors()
        self.library_panel.refresh()

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

        # Each combo stores the engine key as item data; labels are display only.
        self.style_combo = QComboBox()
        for style in STYLE_ORDER:
            self.style_combo.addItem(STYLE_LABELS[style], style)
        layout.addWidget(_labeled_field("Style", self.style_combo))
        layout.addWidget(_hairline(vertical=True))

        self.palette_combo = QComboBox()
        for key in PALETTES:
            self.palette_combo.addItem(key.capitalize(), key)
        layout.addWidget(_labeled_field("Palette", self.palette_combo))
        layout.addWidget(_hairline(vertical=True))

        self.size_combo = QComboBox()
        for key, (width, height) in SIZES.items():
            self.size_combo.addItem(f"{key} · {width} x {height}", key)
        self.size_combo.setCurrentIndex(self.size_combo.findData(DEFAULT_SIZE_KEY))
        layout.addWidget(_labeled_field("Size", self.size_combo))
        layout.addWidget(_hairline(vertical=True))

        self.quiet_combo = QComboBox()
        for zone in QUIET_ZONES:
            self.quiet_combo.addItem(zone.capitalize(), zone)
        layout.addWidget(_labeled_field("Quiet zone", self.quiet_combo))

        layout.addStretch(1)

        self.seed_field = SeedField(DEFAULT_SEED)
        layout.addWidget(_labeled_field("Seed", self.seed_field))

        self.reroll_dial = RerollDial()
        self.reroll_dial.rerolled.connect(self._on_reroll)
        layout.addWidget(self.reroll_dial)

        self.generate_button = QPushButton("Generate")
        self.generate_button.setObjectName("generate")
        self.generate_button.setCursor(Qt.PointingHandCursor)
        self.generate_button.clicked.connect(self._on_generate)
        layout.addWidget(self.generate_button)

        # Connected here (rather than after _build_main_area) relies on
        # _on_style_changed only firing on user interaction, since
        # self.style_panel doesn't exist yet at this point in __init__.
        self.style_combo.currentIndexChanged.connect(self._on_style_changed)
        return rail

    def _build_main_area(self) -> QWidget:
        area = QWidget()
        layout = QHBoxLayout(area)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(20)

        preview_column = QVBoxLayout()
        preview_column.setSpacing(10)

        self.preview_pane = PreviewPane()
        preview_column.addWidget(self.preview_pane, 1)

        self.progress_track = ProgressTrack()
        preview_column.addWidget(self.progress_track)

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

        self.set_all_button = QPushButton("Set on all monitors")
        self.set_all_button.setObjectName("setWallpaper")
        self.set_all_button.setCursor(Qt.PointingHandCursor)
        self.set_all_button.setEnabled(False)
        self.set_all_button.setToolTip("Applies the displayed full-resolution render to all monitors.")
        self.set_all_button.clicked.connect(self._on_set_all)
        layout.addWidget(self.set_all_button)
        # One chip per detected monitor; filled by refresh_monitors().
        self.monitor_bar = QHBoxLayout()
        self.monitor_bar.setSpacing(10)
        layout.addLayout(self.monitor_bar)
        self.render_status = QLabel("Generate a wallpaper to get started.")
        self.render_status.setProperty("role", "field-label")
        self.render_status.setWordWrap(True)
        layout.addWidget(self.render_status, 1)
        return row

    def _build_library_row(self) -> QWidget:
        self.library_panel = LibraryPanel(self.library)
        self.library_panel.load_requested.connect(self._load_library_item)
        self.library_panel.rerender_requested.connect(self._rerender_library_item)
        self.library_panel.deleted.connect(self._on_library_deleted)
        self.library_panel.message.connect(self.render_status.setText)
        return self.library_panel

    def _connect_controller(self) -> None:
        self.controller.preview_ready.connect(self.preview_pane.show_image)
        self.controller.full_ready.connect(self._on_full_ready)
        self.controller.failed.connect(self._on_failed)
        self.controller.progress.connect(self._on_progress)
        self.controller.busy_changed.connect(self._on_busy_changed)
        self.controller.library_changed.connect(self.library_panel.refresh)

    def current_spec(self) -> RenderSpec:
        size = self.size_combo.currentData()
        width, height = SIZES[size] if isinstance(size, str) else size
        return RenderSpec(
            style=self.style_combo.currentData(),
            width=width,
            height=height,
            palette=self.palette_combo.currentData(),
            seed=self.seed_field.seed(),
            quiet_zone=self.quiet_combo.currentData(),
            **self.style_panel.values(),
        )

    def load_spec(self, spec: RenderSpec) -> None:
        """Restore controls without starting a render."""
        self.style_combo.setCurrentIndex(self.style_combo.findData(spec.style))
        self.palette_combo.setCurrentIndex(self.palette_combo.findData(spec.palette))
        self.quiet_combo.setCurrentIndex(self.quiet_combo.findData(spec.quiet_zone))
        size_key = next((key for key, size in SIZES.items() if size == (spec.width, spec.height)), None)
        data = size_key if size_key is not None else (spec.width, spec.height)
        index = self.size_combo.findData(data)
        if index < 0:
            self.size_combo.addItem(f"Custom · {spec.width} x {spec.height}", data)
            index = self.size_combo.count() - 1
        self.size_combo.setCurrentIndex(index)
        self.seed_field.set_seed(spec.seed)
        self.style_panel.load_spec(spec)

    def _load_library_item(self, item_id: str) -> None:
        try:
            entry = self.library.get(item_id)
            self.load_spec(entry.spec)
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.render_status.setText(f"Could not load wallpaper: {exc}")
            return
        self._pending_monitor = None
        self._requested_spec = entry.spec
        self._clear_render()
        self.render_status.setText("Loading saved wallpaper…")
        self._loading_id = item_id
        self.controller.load(self.library.image_path(item_id))

    def _rerender_library_item(self, item_id: str, size_key: str) -> None:
        try:
            spec = self.library.get(item_id).spec.at(*SIZES[size_key])
            self.load_spec(spec)
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.render_status.setText(f"Could not re-render wallpaper: {exc}")
            return
        self._on_generate()

    def _on_library_deleted(self, item_id: str) -> None:
        # A pending load of this item must not re-enable setting a deleted image.
        if self._loading_id == item_id or (
            self._render_path is not None and self._render_path.stem == item_id
        ):
            self.controller.invalidate()
            self._pending_monitor = None
            self._loading_id = None
            self._clear_render()

    def _on_generate(self) -> None:
        spec = self.current_spec()
        self._loading_id = None
        self._pending_monitor = None
        self._requested_spec = spec
        self._clear_render()
        self.render_status.setText("Rendering preview…")
        self.controller.submit(spec)

    def _on_full_ready(self, image, path: Path) -> None:
        self._render_path = path
        self._render_size = (image.width(), image.height())
        self._render_spec = self._requested_spec
        self._loading_id = None
        self.preview_pane.show_image(image)
        self._update_set_controls()
        self.render_status.setText(f"Ready · {image.width()} × {image.height()}")
        monitor, self._pending_monitor = self._pending_monitor, None
        if monitor is not None:
            self._set_on_monitor(monitor)

    def _on_failed(self, message: str) -> None:
        self._pending_monitor = None
        self._loading_id = None
        self._clear_render()
        self.preview_pane.show_error(message)
        self.render_status.setText(f"Generation failed: {message}")

    def _clear_render(self) -> None:
        self._render_path = None
        self._render_size = None
        self._render_spec = None
        self._update_set_controls()

    def _update_set_controls(self) -> None:
        ready = self._render_path is not None
        self.set_all_button.setEnabled(ready)
        for chip, monitor in zip(self.monitor_chips, self.monitors):
            chip.setEnabled(ready)
            # Lit when the displayed render is already this monitor's native size.
            chip.set_active(ready and self._render_size == monitor.size)

    # -- monitors -----------------------------------------------------------

    def _watch_screens(self) -> None:
        self._monitor_timer = QTimer(self)
        self._monitor_timer.setSingleShot(True)
        self._monitor_timer.setInterval(MONITOR_REFRESH_DELAY_MS)
        self._monitor_timer.timeout.connect(self.refresh_monitors)
        app = QGuiApplication.instance()
        app.screenAdded.connect(self._on_screen_added)
        app.screenRemoved.connect(self._schedule_monitor_refresh)
        for screen in app.screens():
            screen.geometryChanged.connect(self._schedule_monitor_refresh)

    def _on_screen_added(self, screen) -> None:
        screen.geometryChanged.connect(self._schedule_monitor_refresh)
        self._schedule_monitor_refresh()

    def _schedule_monitor_refresh(self, *_) -> None:
        self._monitor_timer.start()

    def refresh_monitors(self) -> None:
        """Re-detect displays, then rebuild the chips and monitor sizes."""
        self.monitors = detect_monitors(_screen_geometries())
        for chip in self.monitor_chips:
            self.monitor_bar.removeWidget(chip)
            chip.deleteLater()
        self.monitor_chips = []
        for monitor in self.monitors:
            chip = MonitorChip(monitor.label, monitor.resolution)
            chip.setToolTip(
                f"Set on {monitor.label}. If the displayed render is a different size, "
                f"it is re-rendered at {monitor.width} × {monitor.height} first."
            )
            chip.clicked.connect(lambda monitor=monitor: self._on_monitor_clicked(monitor))
            self.monitor_bar.addWidget(chip)
            self.monitor_chips.append(chip)
        if self._pending_monitor not in self.monitors:
            self._pending_monitor = None
        self._update_monitor_sizes()
        self._update_set_controls()

    def _update_monitor_sizes(self) -> None:
        """Offer each monitor's native resolution at the top of the size list."""
        combo = self.size_combo
        current = combo.currentData()
        for index in reversed(range(combo.count())):
            if combo.itemData(index, MONITOR_ITEM_ROLE):
                combo.removeItem(index)
        for index, monitor in enumerate(self.monitors):
            combo.insertItem(index, f"{monitor.label} · {monitor.width} x {monitor.height}", monitor.size)
            combo.setItemData(index, True, MONITOR_ITEM_ROLE)
        if self.monitors:
            combo.insertSeparator(len(self.monitors))
            combo.setItemData(len(self.monitors), True, MONITOR_ITEM_ROLE)
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else combo.findData(DEFAULT_SIZE_KEY))

    def _on_monitor_clicked(self, monitor: Monitor) -> None:
        if self._render_path is None:
            return
        if self._render_size == monitor.size:
            self._set_on_monitor(monitor)
            return
        if self._render_spec is None:
            self.render_status.setText("Generate again to render this wallpaper for that monitor.")
            return
        # Same design at the monitor's physical size; set it once it is saved.
        self.load_spec(self._render_spec.at(*monitor.size))
        self._on_generate()
        self._pending_monitor = monitor
        self.render_status.setText(
            f"Rendering {monitor.width} × {monitor.height} for {monitor.label}…"
        )

    # -- setting the wallpaper ----------------------------------------------

    def _on_set_all(self) -> None:
        self._apply(lambda path: set_on_all_monitors(path), "all monitors")

    def _set_on_monitor(self, monitor: Monitor) -> None:
        self._apply(lambda path: set_on_monitor(path, monitor.device_path), monitor.label)

    def _apply(self, set_wallpaper, where: str) -> None:
        path = self._render_path
        if path is None:
            return
        try:
            set_wallpaper(path)
        except OSError as exc:
            self.render_status.setText(f"Could not set wallpaper: {exc}")
            return
        try:
            self.library.mark_set(path.stem)
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.render_status.setText(f"Wallpaper set; could not update library: {exc}")
        else:
            self.render_status.setText(f"Wallpaper set on {where}.")

    def closeEvent(self, event) -> None:
        self._monitor_timer.stop()
        # Keep the controller and its signal objects alive until workers finish.
        self.controller.wait_for_done()
        super().closeEvent(event)

    def _on_style_changed(self, index: int) -> None:
        self.style_panel.set_style(self.style_combo.itemData(index))

    def _on_reroll(self) -> None:
        self.seed_field.set_seed(random.randint(0, 99_999_999))
        self._on_generate()

    def _on_progress(self, fraction: float, note: str) -> None:
        self.progress_track.set_fraction(fraction)
        self.render_status.setText(note)

    def _on_busy_changed(self, busy: bool) -> None:
        if not busy:
            self.progress_track.set_fraction(0.0)
