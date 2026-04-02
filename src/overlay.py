"""
OCR-TRANSLATE — Şeffaf Overlay Penceresi (Sovereign & UIBS Hybrid)
MORT ve Universal Info Tool mantığıyla çalışan,
tespit edilen metnin tam üzerine (veya yanına) yerleşen premium kartlar.
"""

import os
import config
from PyQt5.QtCore import Qt, QRectF, QPoint
from PyQt5.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt5.QtWidgets import (
    QWidget,
    QApplication,
    QVBoxLayout,
    QLabel,
    QFrame,
    QGraphicsDropShadowEffect,
)


class TranslationBlockCard(QWidget):
    """
    Universal Info Box Mantığında Çalışan Bağımsız Kart.
    Neden Bağımsız? -> Wayland'de 'Always on Top' garantisi ve Focus yönetimi için.
    """

    def __init__(
        self, parent, text: str, src_text: str, rect: QRectF, bg_color: tuple
    ) -> None:
        super().__init__(parent)
        self.text = text
        self.src_text = src_text
        self._bg_tuple = bg_color
        self._is_dragging = False
        self._drag_start_pos = QPoint()

        # UIBS STANDARTLARI: Her zaman en üstte, fokus almaz, görev çubuğunda görünmez.
        self.setWindowFlags(
            Qt.ToolTip
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput  # Tıklamayı alt pencereye (tarayıcıya) geçirir
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)

        self._setup_ui(rect)

    def _setup_ui(self, rect: QRectF) -> None:
        # Konumlandırma: OCR bloğunun tam üzerine (veya çok az üstüne)
        self.setGeometry(
            int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height())
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self.container = QFrame()
        r, g, b = self._bg_tuple[:3]
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
        text_color = "#FFFFFF" if luminance < 128 else "#000000"
        src_color = "rgba(255,255,255,140)" if luminance < 128 else "rgba(0,0,0,140)"

        # Premium Styling (UIBS Style)
        bg_css = f"rgba({r}, {g}, {b}, 245)"
        self.container.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_css};
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.15);
            }}
        """)

        c_layout = QVBoxLayout(self.container)
        c_layout.setContentsMargins(8, 6, 8, 6)
        c_layout.setSpacing(2)

        # 1. Kaynak Metin (Küçük ve şeffaf)
        if config.SHOW_SOURCE_TEXT and self.src_text:
            src_lbl = QLabel(self.src_text)
            src_lbl.setWordWrap(True)
            src_lbl.setAlignment(Qt.AlignCenter)
            src_lbl.setStyleSheet(
                f"color: {src_color}; font-size: 9px; font-weight: 400; background: transparent; border: none;"
            )
            c_layout.addWidget(src_lbl)

        # 2. Çeviri Metni
        self.label = QLabel(self.text)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignCenter)

        # Font Fitting
        font = self._get_fitted_font(self.text, rect)
        self.label.setFont(font)
        self.label.setStyleSheet(
            f"color: {text_color}; background: transparent; border: none;"
        )
        c_layout.addWidget(self.label)

        layout.addWidget(self.container)

        # Shadow (UIBS Premium Look)
        if rect.width() > 30:
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(15)
            shadow.setColor(QColor(0, 0, 0, 180))
            shadow.setOffset(0, 3)
            try:
                self.container.setGraphicsEffect(shadow)
            except Exception:
                pass

    # region Movement Logic
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._drag_start_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_start_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        event.accept()

    # endregion

    def _get_fitted_font(self, text: str, rect: QRectF) -> QFont:
        base_size = config.OVERLAY_FONT_SIZE
        max_w = rect.width() - 16
        max_h = rect.height() - 12
        if max_w <= 0 or max_h <= 0:
            return QFont(config.OVERLAY_FONT_FAMILY, 8)

        best_size = 8
        low, high = 8, base_size
        while low <= high:
            mid = (low + high) // 2
            f = QFont(config.OVERLAY_FONT_FAMILY, mid, QFont.Bold)
            metrics = QFontMetrics(f)
            text_rect = metrics.boundingRect(
                0, 0, int(max_w), 1000, Qt.AlignCenter | Qt.TextWordWrap, text
            )
            if text_rect.height() <= max_h:
                best_size = mid
                low = mid + 1
            else:
                high = mid - 1
        return QFont(config.OVERLAY_FONT_FAMILY, best_size, QFont.Bold)


class TranslationOverlay(QWidget):
    """
    Ana Pencere (Manager).
    Wayland kuralı: Parent window 'visible' ama 'transient' olmalı.
    """

    def __init__(self, region) -> None:
        super().__init__()
        self._region = region
        self._text = ""
        self._block_widgets = []

        # Manager Ayarları: Görünmez ama aktif
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.01)
        self.setGeometry(0, 0, 1, 1)  # UIBS Style: 0,0'da minik parent
        self.show()

    def update_text(self, text: str) -> None:
        """Dashboard'dan/Klavye'den gelen tekil mesajları (Loading vb.) yönetir."""
        # TODO: Alttaki sinematik barı hâlâ kullanmak isteyebiliriz, şimdilik sessiz.
        pass

    def update_blocks(self, blocks: list) -> None:
        """OCR tarafından tespit edilen tüm blokları bağımsız kartlar olarak render eder."""
        # Temizlik
        for w in self._block_widgets:
            w.hide()
            w.deleteLater()
        self._block_widgets.clear()

        if config.OVERLAY_MODE != "inplace":
            return

        for b in blocks:
            bx = b["box"]
            # Koordinatları Bölgeye (Region) Göre Hesapla
            # bx: [x, y, w, h] - region: {left, top, width, height}

            # ÖNEMLİ: Eğer capture tüm ekran (spectacle) üzerinden yapılıyorsa
            # ve biz bu görüntüyü kırpıp OCR'a sokuyorsak, bx zaten yereldir.
            # Ama capture_region fonksiyonu bazen tüm ekranı döndürüp içinden
            # sadece ilgili kısmı kırpıp worker'a veriyor.

            # Eğer bx koordinatları zaten global ise (ekran geneli), region eklemeye gerek yok.
            # Ancak worker.py'de image = capture_region(...) dönen görüntü 'kırpılmış' haldedir.
            # Dolayısıyla bx, bu kırpılmış görüntüye göre yereldir [0,0] sol üst kabul eder.

            rect = QRectF(
                float(bx[0]) + float(self._region["left"]),
                float(bx[1]) + float(self._region["top"]),
                float(bx[2]),
                float(bx[3]),
            ).adjusted(-4, -4, 4, 4)  # Biraz ferahlık payı

            # Kartı Oluştur (Parent None yaparak gerçek bağımsız pencere yapalım)
            card = TranslationBlockCard(
                None, b["text"], b.get("src_text", ""), rect, b.get("bg", (0, 0, 0))
            )
            card.show()
            card.raise_()  # En öne getir
            self._block_widgets.append(card)

    def update_region(self, region):
        self._region = region

    def closeEvent(self, event):
        for w in self._block_widgets:
            w.close()
        super().closeEvent(event)
