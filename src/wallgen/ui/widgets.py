from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QIntValidator, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from wallgen.ui import theme


class StatusDot(QWidget):
    """A small circular status LED (power, armed, idle, or a palette tag)."""

    def __init__(self, color: str, glow: bool = False, diameter: int = 8, parent: QWidget | None = None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(diameter, diameter)
        if glow:
            effect = QGraphicsDropShadowEffect(self)
            effect.setBlurRadius(10)
            effect.setColor(QColor(color))
            effect.setOffset(0, 0)
            self.setGraphicsEffect(effect)

    def color(self) -> str:
        return self._color

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(self._color)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(self.rect())
        painter.end()


MAX_SEED = 2**31 - 1


class SeedField(QFrame):
    """A recessed, monospace, digits-only field for the render seed."""

    def __init__(self, seed: int = 0, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("seedField")
        self.setFixedWidth(150)
        self.setStyleSheet(
            f"QFrame#seedField {{ background: {theme.BG_SEED}; border: 1px solid {theme.HAIRLINE};"
            f" border-radius: 3px; }}"
            f"QFrame#seedField QLineEdit {{ background: transparent; border: none; padding: 0;"
            f" color: {theme.TEXT_PRIMARY}; font-family: {theme.FONT_MONO}; font-size: 14px; }}"
        )
        self._edit = QLineEdit(str(seed))
        self._edit.setValidator(QIntValidator(0, MAX_SEED, self._edit))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.addWidget(self._edit)

    def seed(self) -> int:
        text = self._edit.text() or "0"
        value = int(text)
        return min(value, MAX_SEED)

    def set_seed(self, seed: int) -> None:
        self._edit.setText(str(seed))


class RerollDial(QAbstractButton):
    """The knurled copper dial that rerolls the seed. Emits `rerolled`."""

    rerolled = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(46, 46)
        self._angle = 0.0
        self._animation = QPropertyAnimation(self, b"angle", self)
        self._animation.setDuration(350)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(360.0)
        self._animation.setEasingCurve(QEasingCurve.OutBack)
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self) -> None:
        self._animation.stop()
        self._animation.start()
        self.rerolled.emit()

    def get_angle(self) -> float:
        return self._angle

    def set_angle(self, value: float) -> None:
        self._angle = value
        self.update()

    angle = Property(float, get_angle, set_angle)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()

        gradient = QRadialGradient(
            rect.center().x() - rect.width() * 0.15,
            rect.center().y() - rect.height() * 0.22,
            rect.width() * 0.8,
        )
        gradient.setColorAt(0.0, QColor(theme.COPPER_LIGHT))
        gradient.setColorAt(0.45, QColor(theme.COPPER))
        gradient.setColorAt(1.0, QColor(theme.COPPER_DARK))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(theme.COPPER_DARK), 1))
        painter.drawEllipse(rect.adjusted(1, 1, -1, -1))

        painter.translate(rect.center())
        painter.rotate(self._angle)
        painter.translate(-rect.center())
        painter.setPen(QPen(QColor(theme.BG_WINDOW), 2.2, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        arrow_rect = QRectF(rect.center().x() - 8, rect.center().y() - 8, 16, 16)
        painter.drawArc(arrow_rect, 20 * 16, 300 * 16)
        painter.end()


class MonitorChip(QFrame):
    """A labeled port on the 'Set on' row — a detected monitor, or 'All'."""

    def __init__(self, name: str, resolution: str, active: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("role", "chip-active" if active else "chip")
        self._active = active

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 8, 16, 8)
        outer.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.addStretch(1)
        dot_color = theme.VERDIGRIS if active else theme.TEXT_MUTED
        top_row.addWidget(StatusDot(dot_color, glow=active))
        outer.addLayout(top_row)

        name_label = QLabel(name)
        name_label.setProperty("role", "value")
        outer.addWidget(name_label)

        if resolution:
            res_label = QLabel(resolution)
            res_label.setProperty("role", "field-label")
            outer.addWidget(res_label)

        self._name_label = name_label

    def is_active(self) -> bool:
        return self._active

    def name_text(self) -> str:
        return self._name_label.text()


class LibraryThumbnail(QFrame):
    """One frame of the library contact sheet."""

    def __init__(self, style_label: str, dot_color: str, art_color: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedWidth(172)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        sprocket_top = QFrame()
        sprocket_top.setProperty("role", "sprocket")
        sprocket_top.setFixedHeight(6)
        outer.addWidget(sprocket_top)

        art = QFrame()
        art.setFixedHeight(88)
        art.setStyleSheet(f"background: {art_color}; border: none;")
        outer.addWidget(art)

        sprocket_bottom = QFrame()
        sprocket_bottom.setProperty("role", "sprocket")
        sprocket_bottom.setFixedHeight(6)
        outer.addWidget(sprocket_bottom)

        caption = QHBoxLayout()
        caption.setSpacing(6)
        caption.addWidget(StatusDot(dot_color))
        label = QLabel(style_label)
        label.setProperty("role", "field-label")
        caption.addWidget(label)
        caption.addStretch(1)
        outer.addLayout(caption)

        self._style_label = style_label

    def style_label(self) -> str:
        return self._style_label


class ProgressTrack(QFrame):
    """The thin track under the preview; a copper fill shows render progress."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(3)
        self._fraction = 0.0

    def fraction(self) -> float:
        return self._fraction

    def set_fraction(self, fraction: float) -> None:
        self._fraction = max(0.0, min(1.0, fraction))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        rect = QRectF(self.rect())
        painter.setBrush(QColor(theme.HAIRLINE))
        painter.drawRoundedRect(rect, 2, 2)
        if self._fraction > 0.0:
            fill = QRectF(rect.left(), rect.top(), rect.width() * self._fraction, rect.height())
            painter.setBrush(QColor(theme.COPPER))
            painter.drawRoundedRect(fill, 2, 2)
        painter.end()
