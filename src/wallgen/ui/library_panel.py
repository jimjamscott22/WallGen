"""A thumbnail library with filtering, load-back and context-menu actions."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget,
    QListWidgetItem, QMenu, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from wallgen.engine import SIZES
from wallgen.store.db import LibraryStore
from wallgen.ui.style_options import STYLE_LABELS


class LibraryPanel(QWidget):
    load_requested = Signal(str)
    rerender_requested = Signal(str, str)
    deleted = Signal(str)
    message = Signal(str)

    def __init__(self, store: LibraryStore, parent=None):
        super().__init__(parent)
        self.store = store
        self._limit = 100
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 12, 28, 16)
        header = QHBoxLayout()
        title = QLabel("Library")
        title.setProperty("role", "field-label")
        header.addWidget(title)
        self.count_label = QLabel()
        self.count_label.setProperty("role", "field-label")
        header.addWidget(self.count_label)
        header.addStretch(1)
        self.favorites = QCheckBox("Favorites only")
        header.addWidget(self.favorites)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search style, palette, seed or text…")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(240)
        self.search.setMaximumWidth(320)
        header.addWidget(self.search)
        self.more = QPushButton("Load more")
        self.more.setObjectName("libraryMore")
        header.addWidget(self.more)
        layout.addLayout(header)

        self.grid = QListWidget()
        self.grid.setObjectName("libraryGrid")
        self.grid.setViewMode(QListView.IconMode)
        self.grid.setResizeMode(QListView.Adjust)
        self.grid.setMovement(QListView.Static)
        self.grid.setIconSize(QSize(164, 92))
        self.grid.setGridSize(QSize(186, 140))
        self.grid.setSpacing(4)
        self.grid.setWordWrap(True)
        self.grid.setMinimumHeight(155)
        self.grid.setMaximumHeight(230)
        self.grid.setContextMenuPolicy(Qt.CustomContextMenu)
        self.grid.setToolTip("Double-click to load. Right-click for library actions.")
        self.grid.itemDoubleClicked.connect(lambda item: self.load_requested.emit(item.data(Qt.UserRole)))
        self.grid.customContextMenuRequested.connect(self._menu)
        layout.addWidget(self.grid)
        self.hint = QLabel("Generate a wallpaper to start your library.")
        self.hint.setProperty("role", "field-label")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(180)
        self._search_timer.timeout.connect(self._filter_changed)
        self.search.textChanged.connect(lambda: self._search_timer.start())
        self.favorites.toggled.connect(self._filter_changed)
        self.more.clicked.connect(self._load_more)

    def _filter_changed(self) -> None:
        self._limit = 100
        self.refresh()

    def _load_more(self) -> None:
        self._limit += 100
        self.refresh()

    def refresh(self) -> None:
        try:
            entries = self.store.list(self.search.text(), self.favorites.isChecked(), self._limit)
        except Exception as exc:
            self.hint.setText(f"Library unavailable: {exc}")
            return
        selected = self.grid.currentItem()
        selected_id = selected.data(Qt.UserRole) if selected else None
        scroll = self.grid.verticalScrollBar().value()
        self.grid.clear()
        for entry in entries:
            spec = entry.spec
            star = "★ " if entry.favorite else ""
            item = QListWidgetItem(
                QIcon(str(self.store.thumbnail_path(entry.id))),
                f"{star}{STYLE_LABELS[spec.style]} · {spec.palette}\n{spec.width} × {spec.height} · {spec.seed}",
            )
            item.setData(Qt.UserRole, entry.id)
            item.setToolTip(f"{entry.created_at}\nSeed {spec.seed}\nDouble-click to load; right-click for actions.")
            item.setSizeHint(QSize(178, 136))
            self.grid.addItem(item)
            if entry.id == selected_id:
                self.grid.setCurrentItem(item)
        self.grid.verticalScrollBar().setValue(scroll)
        self.count_label.setText(f"{len(entries)} shown")
        self.more.setEnabled(len(entries) >= self._limit)
        self.hint.setText(
            "Double-click to load · Right-click for favorite, re-render, folder and delete."
            if entries else "No matching wallpapers." if self.search.text() or self.favorites.isChecked()
            else "Generate a wallpaper to start your library."
        )

    def toggle_favorite(self, item_id: str) -> None:
        try:
            entry = self.store.get(item_id)
            self.store.favorite(item_id, not entry.favorite)
            self.refresh()
        except Exception as exc:
            self.message.emit(f"Could not update favorite: {exc}")

    def delete_item(self, item_id: str) -> None:
        if QMessageBox.question(
            self, "Delete wallpaper?",
            "Remove this wallpaper from the library? Previously applied images are kept on disk for Windows.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        try:
            retained = self.store.delete(item_id)
        except Exception as exc:
            self.message.emit(f"Could not delete wallpaper: {exc}")
            return
        self.refresh()
        self.deleted.emit(item_id)
        self.message.emit("Removed from library; desktop image kept." if retained else "Wallpaper deleted.")

    def open_folder(self, item_id: str) -> None:
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.image_path(item_id).parent))):
            self.message.emit("Could not open the wallpaper folder.")

    def _menu(self, position) -> None:
        item = self.grid.itemAt(position)
        if item is None:
            return
        item_id = item.data(Qt.UserRole)
        menu = QMenu(self)
        menu.addAction("Load wallpaper", lambda: self.load_requested.emit(item_id))
        menu.addAction("Toggle favorite", lambda: self.toggle_favorite(item_id))
        sizes = menu.addMenu("Re-render at…")
        for key, (width, height) in SIZES.items():
            sizes.addAction(f"{key} · {width} × {height}",
                            lambda checked=False, size=key: self.rerender_requested.emit(item_id, size))
        menu.addAction("Open folder", lambda: self.open_folder(item_id))
        menu.addSeparator()
        menu.addAction("Delete…", lambda: self.delete_item(item_id))
        menu.exec(self.grid.viewport().mapToGlobal(position))
