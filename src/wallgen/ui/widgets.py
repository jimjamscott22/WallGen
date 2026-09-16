from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
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


class SeedField(QFrame):
    """A recessed, monospace readout for the render seed."""

    def __init__(self, seed: int = 0, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {theme.BG_SEED}; border: 1px solid {theme.HAIRLINE}; border-radius: 3px;"
        )
        self._label = QLabel(str(seed))
        self._label.setProperty("role", "value")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.addWidget(self._label)

    def seed(self) -> int:
        return int(self._label.text())

    def set_seed(self, seed: int) -> None:
        self._label.setText(str(seed))


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
