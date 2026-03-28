"""
OCR-TRANSLATE — Şeffaf Overlay Penceresi
AAA Standartlarında, sinematik altyazı deneyimi.
"""

import os
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
    QLinearGradient,
)
from PyQt5.QtWidgets import QWidget, QApplication

import config


class TranslationOverlay(QWidget):
    """
    Şeffaf, elit görünümlü glassmorphism overlay penceresi.
    """

    def __init__(self, region) -> None:
        super().__init__()
        self._region = region
        self._text = ""
        self._blocks = []  # List[dict[text, box, bg]]
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
        if config.OVERLAY_MODE == "inplace":
            return  # In-place modunda block sinyalini beklerizer
        self._text = text.strip()
        self._blocks = []
        if self._text:
            self._update_geometry()
            if not self.isVisible():
                self.show()
        else:
            self.hide()
        self.update()

    def update_blocks(self, blocks: list) -> None:
        """MORT-Style: Koordinatlı blokları günceller."""
        if config.OVERLAY_MODE != "inplace":
            return
        self._blocks = blocks
        if self._blocks:
            # Tüm ekranı kapsayacak şekilde genişle (Bloklar bu alanın içindedir)
            screen = QApplication.primaryScreen()
            if screen:
                geom = screen.geometry()
                self.setGeometry(0, 0, geom.width(), geom.height())
            else:
                self.setGeometry(
                    0,
                    0,
                    self._region["left"] + self._region["width"],
                    self._region["top"] + self._region["height"],
                )
            if not self.isVisible():
                self.show()
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
        rect = metrics.boundingRect(
            0, 0, max_w - 2 * padding, 1000, Qt.AlignLeft | Qt.TextWordWrap, self._text
        )

        if config.OVERLAY_MODE == "inplace":
            # Orijinal metnin tam üzerine (MORT Style)
            x = self._region["left"]
            y = self._region["top"]
            w = self._region["width"]
            h = self._region["height"]
        else:
            # Seçili alanın altına (Sinematik mod)
            w = min(rect.width() + 2 * padding + 20, max_w)
            h = rect.height() + 2 * padding + 10
            x = self._region["left"] + (self._region["width"] - w) // 2
            y = self._region["top"] + self._region["height"] + config.OVERLAY_MARGIN_TOP

        self.setGeometry(int(x), int(y), int(w), int(h))

    def paintEvent(self, a0) -> None:
        if not self._text and not self._blocks:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        # 1. MORT-Style Multi-block Rendering
        if self._blocks:
            for b in self._blocks:
                txt = b["text"]
                bx = b["box"]  # [x, y, w, h] (Orijinal resimdeki)
                bg = b.get("bg", (0, 0, 0))

                # Koordinatları overlay penceresine uyarla
                rect = QRectF(bx[0], bx[1], bx[2], bx[3]).adjusted(-5, -2, 5, 2)

                # Arka Plan Maskeleme (Natural Masking)
                p.setBrush(QColor(*bg, 230))  # Hafif şeffaf ama kapatıcı
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(rect, 5, 5)

                # Dinamik font boyutu: Blok boyutuna ve metin uzunluğuna göre ayarla
                font = self._get_fitted_font(txt, rect)
                p.setFont(font)

                # Metin Çizimi (Outline + Fill)
                self._draw_outlined_text(p, rect, txt, font)

        # 2. Klasik Tek Blok Rendering (Legacy/Cinema Mode)
        elif self._text:
            font = self._get_font()
            p.setFont(font)

            bg_color = QColor(config.OVERLAY_BG_COLOR)
            path = QPainterPath()
            path.addRoundedRect(QRectF(self.rect()), 15, 15)
            p.fillPath(path, bg_color)

            padding = config.OVERLAY_PADDING
            rect = self.rect().adjusted(padding, padding, -padding, -padding)

            self._draw_outlined_text(p, QRectF(rect), self._text, font)

        p.end()

    def _get_fitted_font(self, text: str, rect: QRectF) -> QFont:
        """Metni verilen dikdörtgen içine sığdıracak font boyutunu hesaplar."""
        base_size = config.OVERLAY_FONT_SIZE
        min_size = max(8, base_size // 3)  # Minimum okunabilir boyut
        max_w = rect.width() - 6  # padding
        max_h = rect.height() - 4

        if max_w <= 0 or max_h <= 0:
            return self._get_font()

        # Binary search ile optimum font boyutu bul
        best_size = min_size
        for size in range(base_size, min_size - 1, -1):
            f = QFont(config.OVERLAY_FONT_FAMILY, size)
            f.setBold(True)
            f.setLetterSpacing(QFont.PercentageSpacing, 105)
            metrics = QFontMetrics(f)
            text_rect = metrics.boundingRect(
                0, 0, int(max_w), int(max_h), Qt.AlignCenter | Qt.TextWordWrap, text
            )
            if text_rect.width() <= max_w and text_rect.height() <= max_h:
                best_size = size
                break

        f = QFont(config.OVERLAY_FONT_FAMILY, best_size)
        f.setBold(True)
        f.setLetterSpacing(QFont.PercentageSpacing, 105)
        return f

    def _draw_outlined_text(
        self, p: QPainter, rect: QRectF, text: str, font: QFont
    ) -> None:
        """Outline efektli metin çizer (offset ile)."""
        p.setFont(font)
        off = max(1, font.pointSize() // 12)  # Font boyutuna göre outline kalınlığı

        # Outline (4 yöne offset ile)
        p.setPen(QColor(config.OVERLAY_OUTLINE_COLOR))
        for dx, dy in [(-off, 0), (off, 0), (0, -off), (0, off)]:
            p.drawText(rect.translated(dx, dy), Qt.AlignCenter | Qt.TextWordWrap, text)

        # Köşe offset'leri (daha belirgin outline için)
        corner_off = max(1, off - 1)
        for dx, dy in [
            (-corner_off, -corner_off),
            (corner_off, -corner_off),
            (-corner_off, corner_off),
            (corner_off, corner_off),
        ]:
            p.drawText(rect.translated(dx, dy), Qt.AlignCenter | Qt.TextWordWrap, text)

        # Ana metin
        p.setPen(QColor(config.OVERLAY_FONT_COLOR))
        p.drawText(rect, Qt.AlignCenter | Qt.TextWordWrap, text)

    def _get_font(self) -> QFont:
        f = QFont(config.OVERLAY_FONT_FAMILY, config.OVERLAY_FONT_SIZE)
        f.setBold(True)
        f.setLetterSpacing(QFont.PercentageSpacing, 105)
        return f

    def update_region(self, region) -> None:
        self._region = region
        self._update_geometry()
        self.update()
