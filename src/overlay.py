"""
OCR-TRANSLATE — Şeffaf Overlay Penceresi
AAA Standartlarında, sinematik altyazı deneyimi.
"""

import os
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QLinearGradient
from PyQt5.QtWidgets import QWidget

import config

class TranslationOverlay(QWidget):
    """
    Şeffaf, elit görünümlü glassmorphism overlay penceresi.
    """

    def __init__(self, region) -> None:
        super().__init__()
        self._region = region
        self._text = ""
        self._setup_window()
        self._update_geometry()

    def _setup_window(self) -> None:
        # Wayland/X11 uyumluluğu
        is_wayland = "wayland" in os.environ.get("XDG_SESSION_TYPE", "").lower()
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        if not is_wayland:
            flags |= Qt.X11BypassWindowManagerHint
            
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

    def update_text(self, text: str) -> None:
        self._text = text.strip()
        if self._text:
            self._update_geometry()
            if not self.isVisible(): self.show()
        else:
            self.hide()
        self.update()

    def _update_geometry(self) -> None:
        font = self._get_font()
        metrics = QFontMetrics(font)
        
        # Maksimum genişlik seçili alan veya min 400px
        max_w = max(self._region["width"], 400)
        padding = config.OVERLAY_PADDING
        
        # Metin alanı hesabı
        rect = metrics.boundingRect(0, 0, max_w - 2 * padding, 1000, Qt.AlignLeft | Qt.TextWordWrap, self._text)
        
        w = min(rect.width() + 2 * padding + 20, max_w)
        h = rect.height() + 2 * padding + 10
        
        x = self._region["left"] + (self._region["width"] - w) // 2
        y = self._region["top"] + self._region["height"] + config.OVERLAY_MARGIN_TOP
        
        self.setGeometry(x, y, int(w), int(h))

    def paintEvent(self, event) -> None:
        if not self._text: return
        
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        # 1. Glassmorphism Background (Gradient & Blur effect emulation)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 12, 12)
        
        # Arka plan gradyanı (Derinlik hissi için)
        bg_grad = QLinearGradient(0, 0, 0, self.height())
        bg_grad.setColorAt(0, QColor(20, 20, 25, 230))
        bg_grad.setColorAt(1, QColor(5, 5, 8, 250))
        
        p.fillPath(path, bg_grad)
        
        # Border (Yumuşak parlayan sınır)
        border_pen = QPen(QColor(255, 255, 255, 30))
        border_pen.setWidth(1)
        p.setPen(border_pen)
        p.drawPath(path)

        # 2. Text Rendering
        p.setFont(self._get_font())
        inner_rect = self.rect().adjusted(config.OVERLAY_PADDING, config.OVERLAY_PADDING, 
                                        -config.OVERLAY_PADDING, -config.OVERLAY_PADDING)
        
        # Drop Shadow Metin (Okunabilirlik için siyah kopya)
        p.setPen(QColor(0, 0, 0, 180))
        p.drawText(inner_rect.adjusted(2, 2, 2, 2), Qt.AlignHCenter | Qt.TextWordWrap, self._text)
        
        # Ana Metin (Vibrant White)
        p.setPen(QColor(config.OVERLAY_FONT_COLOR))
        p.drawText(inner_rect, Qt.AlignHCenter | Qt.TextWordWrap, self._text)
        
        p.end()

    def _get_font(self) -> QFont:
        f = QFont(config.OVERLAY_FONT_FAMILY, config.OVERLAY_FONT_SIZE)
        f.setBold(True)
        f.setLetterSpacing(QFont.PercentageSpacing, 105)
        return f

    def update_region(self, region) -> None:
        self._region = region
        self._update_geometry()
        self.update()
