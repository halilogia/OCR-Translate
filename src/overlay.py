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

        # Temel bayraklar - WindowTransparentForInput Wayland'da mouse passthrough için kritik
        flags = (
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
        )

        if is_wayland:
            # Wayland: Tool penceresi
            flags |= Qt.Tool
        else:
            # X11: Klasik bypass
            flags |= Qt.Tool | Qt.X11BypassWindowManagerHint

        self.setWindowFlags(flags)

        # Şeffaflık attribute'ları
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        # Input region'ı boş yap - tüm input'lar altındaki pencereye geçsin
        if is_wayland:
            # KDE Wayland için ek input passthrough
            self.setWindowOpacity(1.0)
            # Mask'ı boş yap - hiçbir piksel input almaz
            from PyQt5.QtGui import QRegion

            self.setMask(QRegion())  # Boş region = tüm input pass-through

        print(f"[OVERLAY] Setup: Wayland={is_wayland}, InputPassthrough=True")

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
        """MORT-Style: Koordinatlı blokları günceller.

        Blok koordinatları yakalanan görüntüye görelidir.
        Overlay seçili bölgenin üzerinde konumlandırılır ve koordinatlar
        region offset ile düzeltilir.
        """
        if config.OVERLAY_MODE != "inplace":
            return

        # Blok koordinatlarını region offset ile düzelt
        adjusted_blocks = []
        for b in blocks:
            bx = b["box"]  # [x, y, w, h] - görüntüye göreli
            adjusted_blocks.append(
                {
                    "text": b["text"],
                    "box": [
                        bx[0] + self._region["left"],  # x + region.left
                        bx[1] + self._region["top"],  # y + region.top
                        bx[2],  # width aynı kalır
                        bx[3],  # height aynı kalır
                    ],
                    "bg": b.get("bg", (0, 0, 0)),
                }
            )

        self._blocks = adjusted_blocks
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
            for idx, b in enumerate(self._blocks):
                txt = b["text"]
                bx = b["box"]  # [x, y, w, h] (Region offset'i uygulanmış)
                bg = b.get("bg", (0, 0, 0))

                # Koordinatları overlay penceresine uyarla
                rect = QRectF(bx[0], bx[1], bx[2], bx[3]).adjusted(-5, -2, 5, 2)

                # Arka Plan Maskeleme (Natural Masking) - Orijinal metni tamamen kapat
                p.setBrush(QColor(*bg, 245))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(rect, 4, 4)

                # Dinamik font boyutu: Blok boyutuna ve metin uzunluğuna göre ayarla
                font = self._get_fitted_font(txt, rect)
                p.setFont(font)

                # Metin Çizimi (Outline + Fill) - Otomatik kontrast
                self._draw_outlined_text(p, rect, txt, font, bg_color=bg)

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

    def _get_contrast_colors(self, bg_color: tuple) -> tuple:
        """Arka plan rengine göre kontrast metin ve outline rengi hesaplar.

        Returns:
            (text_color, outline_color) - QColor tuple
        """
        r, g, b = bg_color[:3]
        # Luminance hesabı (ITU-R BT.709)
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b

        if luminance > 128:
            # Açık arka plan -> Koyu metin
            return (QColor(0, 0, 0), QColor(255, 255, 255))
        else:
            # Koyu arka plan -> Açık metin
            return (QColor(255, 255, 255), QColor(0, 0, 0))

    def _draw_outlined_text(
        self, p: QPainter, rect: QRectF, text: str, font: QFont, bg_color: tuple = None
    ) -> None:
        """Outline efektli metin çizer (offset ile).

        Args:
            bg_color: Arka plan rengi (r, g, b) - otomatik kontrast için
        """
        p.setFont(font)
        off = max(1, font.pointSize() // 12)  # Font boyutuna göre outline kalınlığı

        # Kontrast renkleri hesapla
        if bg_color:
            text_color, outline_color = self._get_contrast_colors(bg_color)
        else:
            text_color = QColor(config.OVERLAY_FONT_COLOR)
            outline_color = QColor(config.OVERLAY_OUTLINE_COLOR)

        # Outline (4 yöne offset ile)
        p.setPen(outline_color)
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
        p.setPen(text_color)
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
