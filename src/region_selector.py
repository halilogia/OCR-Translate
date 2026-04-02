"""
OCR-TRANSLATE — Bölge Seçimi Modülü
PyQt5 ile tam ekran yarı saydam pencere üzerinden fare ile dikdörtgen alan seçimi.
Wayland ve X11 uyumlu.
"""

import os
import sys
from typing import Optional

from PyQt5.QtCore import QEventLoop, QPoint, QRect, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PyQt5.QtWidgets import QApplication, QWidget

from screen_capture import Region, get_full_screen_region
from i18n import _


def _is_wayland() -> bool:
    """Wayland oturumunda mıyız?"""
    return "wayland" in os.environ.get("XDG_SESSION_TYPE", "").lower()


class RegionSelector(QWidget):
    """
    Tam ekran yarı saydam pencere.
    Fare ile dikdörtgen alan çizilir veya tam ekran seçilir.
    """

    # Seçim tamamlandığında veya iptal edildiğinde sinyal gönderir
    selection_done = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._origin: Optional[QPoint] = None
        self._current: Optional[QPoint] = None
        self._selected_region: Optional[Region] = None
        self._is_selecting = False

        self._setup_window()

    def _setup_window(self) -> None:
        """Pencere özelliklerini ayarlar (Wayland/X11 uyumlu)."""
        if _is_wayland():
            # Wayland: X11BypassWindowManagerHint kullanılamaz
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        else:
            # X11: Bypass ile tam kontrol
            self.setWindowFlags(
                Qt.FramelessWindowHint
                | Qt.WindowStaysOnTopHint
                | Qt.X11BypassWindowManagerHint
            )

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(QCursor(Qt.CrossCursor))

        # Tüm ekranı kapla
        screen_region = get_full_screen_region()
        self.setGeometry(
            screen_region["left"],
            screen_region["top"],
            screen_region["width"],
            screen_region["height"],
        )

    def paintEvent(self, event) -> None:  # noqa: N802
        """Yarı saydam arka plan ve seçim dikdörtgeni çizer."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Yarı saydam koyu arka plan
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))

        # Yönlendirme metni
        painter.setPen(QPen(QColor(255, 255, 255, 220), 1))
        font = QFont("Sans", 16)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            self.rect(),
            Qt.AlignTop | Qt.AlignHCenter,
            "\n\n  " + _("select_area_instructions"),
        )

        # Seçim dikdörtgeni
        if self._origin and self._current:
            selection = QRect(self._origin, self._current).normalized()

            # Seçili alanı temizle (şeffaf yap)
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(selection, Qt.transparent)

            # Seçim kenarları
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            pen = QPen(QColor(0, 200, 255), 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(selection)

            # Boyut bilgisi
            size_text = f"{selection.width()} x {selection.height()}"
            painter.setPen(QPen(QColor(0, 200, 255, 220), 1))
            font = QFont("Sans", 11)
            painter.setFont(font)
            painter.drawText(
                selection.bottomRight().x() - 100,
                selection.bottomRight().y() + 18,
                size_text,
            )

        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Fare basıldığında seçim başlar."""
        if event.button() == Qt.LeftButton:
            self._origin = event.pos()
            self._current = event.pos()
            self._is_selecting = True
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        """Fare hareket ettikçe seçim güncellenir."""
        if self._is_selecting:
            self._current = event.pos()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """Fare bırakıldığında seçim tamamlanır."""
        if event.button() == Qt.LeftButton and self._is_selecting:
            self._is_selecting = False
            if self._origin and self._current:
                rect = QRect(self._origin, self._current).normalized()

                # Minimum boyut kontrolü (en az 50x20 piksel)
                if rect.width() >= 50 and rect.height() >= 20:
                    self._selected_region = Region(
                        top=rect.y() + self.geometry().y(),
                        left=rect.x() + self.geometry().x(),
                        width=rect.width(),
                        height=rect.height(),
                    )
                    self._finish()
                else:
                    # Çok küçük seçim, sıfırla
                    self._origin = None
                    self._current = None
                    self.update()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """Klavye kısayolları."""
        if event.key() == Qt.Key_Escape:
            self._selected_region = None
            self._finish()
        elif event.key() == Qt.Key_F:
            # Tam ekran seçimi
            self._selected_region = get_full_screen_region()
            self._finish()

    def _finish(self) -> None:
        """Seçimi tamamlar — sinyal gönder ve pencereyi kapat."""
        self.hide()
        self.selection_done.emit()

    def get_region(self) -> Optional[Region]:
        """Seçilen bölgeyi döner. Seçim yapılmadıysa None."""
        return self._selected_region


def select_region() -> Optional[Region]:
    """
    Bölge seçimi penceresini açar ve kullanıcının seçtiği bölgeyi döner.
    Mevcut bir QApplication varsa onu kullanır, yoksa yeni oluşturur.
    """
    app = QApplication.instance()
    created_app = False
    if app is None:
        app = QApplication(sys.argv)
        created_app = True

    selector = RegionSelector()
    selector.showFullScreen()

    if created_app:
        selector.selection_done.connect(app.quit)
        app.exec_()
    else:
        # Event loop zaten çalışıyorsa lokal döngü
        loop = QEventLoop()
        selector.selection_done.connect(loop.quit)
        loop.exec_()

    return selector.get_region()
