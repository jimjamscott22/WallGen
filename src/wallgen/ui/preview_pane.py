"""The preview viewport: paints a QImage aspect-fit and crossfades between images."""

from __future__ import annotations

from PySide6.QtCore import QAbstractAnimation, QRect, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from wallgen.ui import theme

FADE_MS = 200
_ERROR_STRIP_HEIGHT = 28


def fit_rect(src_w: int, src_h: int, dst: QRect) -> QRect:
    """The largest rect with the source's aspect ratio that fits inside `dst`, centered."""
    if src_w <= 0 or src_h <= 0 or dst.width() <= 0 or dst.height() <= 0:
        return QRect()
    scale = min(dst.width() / src_w, dst.height() / src_h)
    width = round(src_w * scale)
    height = round(src_h * scale)
    x = dst.x() + (dst.width() - width) // 2
    y = dst.y() + (dst.height() - height) // 2
    return QRect(x, y, width, height)


class PreviewPane(QWidget):
    def __init__(self, fade_ms: int = FADE_MS, parent: QWidget | None = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._pixmap: QPixmap | None = None
        self._previous: QPixmap | None = None
        self._fade = 1.0
        self._error = ""

        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(fade_ms)
        self._animation.valueChanged.connect(self._on_fade_step)

    # -- public API ---------------------------------------------------------

    def show_image(self, image: QImage) -> None:
        """Fade `image` in over whatever is currently shown. GUI thread only."""
        self._previous = self._pixmap
        self._pixmap = QPixmap.fromImage(image)
        self._error = ""
        self._fade = 0.0
        self._animation.stop()
        self._animation.start()
        self.update()

    def show_error(self, message: str) -> None:
        """Overlay a short error line; the last good image stays visible."""
        self._error = message
        self.update()

    def has_image(self) -> bool:
        return self._pixmap is not None

    def image_size(self) -> QSize:
        return self._pixmap.size() if self._pixmap is not None else QSize()

    def error_text(self) -> str:
        return self._error

    def is_fading(self) -> bool:
        return self._animation.state() == QAbstractAnimation.Running

    # -- internals ----------------------------------------------------------

    def _on_fade_step(self, value) -> None:
        self._fade = float(value)
        if self._fade >= 1.0:
            self._previous = None
        self.update()

    def _draw_pixmap(self, painter: QPainter, pixmap: QPixmap, inner: QRect) -> None:
        target = fit_rect(pixmap.width(), pixmap.height(), inner)
        painter.drawPixmap(target, pixmap)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor(theme.HAIRLINE), 1))
        painter.setBrush(QColor(theme.BG_VIEWPORT))
        painter.drawRoundedRect(frame, 4, 4)

        inner = self.rect().adjusted(1, 1, -1, -1)
        if self._pixmap is None:
            painter.setPen(QColor(theme.TEXT_MUTED))
            painter.drawText(inner, Qt.AlignCenter, "Press Generate")
        else:
            if self._previous is not None:
                self._draw_pixmap(painter, self._previous, inner)
            painter.setOpacity(self._fade)
            self._draw_pixmap(painter, self._pixmap, inner)
            painter.setOpacity(1.0)

        if self._error:
            strip = QRect(inner.left(), inner.bottom() - _ERROR_STRIP_HEIGHT + 1, inner.width(), _ERROR_STRIP_HEIGHT)
            painter.fillRect(strip, QColor(theme.BG_WINDOW))
            font = QFont()
            font.setFamilies(["JetBrains Mono", "Consolas"])
            font.setPixelSize(12)
            painter.setFont(font)
            painter.setPen(QColor(theme.TEXT_MUTED))
            text_rect = strip.adjusted(10, 0, -10, 0)
            elided = painter.fontMetrics().elidedText(self._error, Qt.ElideRight, text_rect.width())
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)
        painter.end()
