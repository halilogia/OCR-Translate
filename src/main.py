import argparse
import logging
import signal
import sys
from typing import Optional

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QApplication, QMenu, QSystemTrayIcon

import config
from cache import TextCache
from ocr_engine import extract_text
from overlay import TranslationOverlay
from region_selector import select_region
from screen_capture import Region, capture_region, get_full_screen_region
from translator import check_ollama_connection, translate
from dashboard import MainDashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("OCR-TRANSLATE")


class OCRTranslateApp:
    """Ana uygulama sınıfı. Tüm bileşenleri orkestre eder."""

    def __init__(self, model: str, interval: int, fullscreen: bool) -> None:
        self._model = model
        self._interval = interval
        self._fullscreen = fullscreen

        self._region: Optional[Region] = None
        self._overlay: Optional[TranslationOverlay] = None
        self._dashboard: Optional[MainDashboard] = None
        self._cache = TextCache()
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)

        self._running = False
        self._last_translation = ""
        self._tick_count = 0

    # region Uygulama Başlatma

    def run(self) -> None:
        """Dashboard'u başlatır ve uygulamayı hazır hale getirir."""
        self._dashboard = MainDashboard(self._model)
        self._dashboard.show()

        # Dashboard sinyallerini bağla
        self._dashboard.start_requested.connect(self.start)
        self._dashboard.stop_requested.connect(self.stop)
        self._dashboard.region_change_requested.connect(self.change_region)
        self._dashboard.model_changed.connect(self._on_model_changed)
        self._dashboard.interval_changed.connect(self._on_interval_changed)

        if self._fullscreen:
            self.start()

    def _on_model_changed(self, model: str) -> None:
        """Dashboard'tan model değişikliği geldiğinde."""
        self._model = model
        logger.info("Aktif model değiştirildi: %s", model)

    def _on_interval_changed(self, interval: int) -> None:
        """Dashboard'tan tarama aralığı değişikliği geldiğinde."""
        self._interval = interval
        if self._running:
            self._timer.setInterval(interval)
        logger.info("Tarama aralığı değiştirildi: %dms", interval)

    def start(self) -> bool:
        """Çeviri döngüsünü başlatır."""
        logger.info("OCR-TRANSLATE başlatılıyor...")

        # Bölge seçimi yoksa zorla
        if self._region is None:
            if self._fullscreen:
                self._region = get_full_screen_region()
            else:
                self._region = select_region()
                if self._region is None:
                    logger.info("Bölge seçimi iptal edildi.")
                    return False

        # Overlay oluştur/güncelle
        if self._overlay is None:
            self._overlay = TranslationOverlay(self._region)
        else:
            self._overlay.update_region(self._region)

        self._overlay.update_text("⏳ OCR-TRANSLATE hazır. Metin bekleniyor...")
        self._overlay.show()

        # Dashboard'taki güncel aralığı oku
        if self._dashboard and hasattr(self._dashboard, "interval_spin"):
            self._interval = self._dashboard.interval_spin.value()

        # Zamanlayıcıyı başlat
        self._timer.start(self._interval)
        self._running = True

        if self._dashboard:
            self._dashboard.set_running_state(True)

        logger.info("Çeviri döngüsü başladı (her %dms)", self._interval)
        return True

    def stop(self) -> None:
        """Çeviri döngüsünü durdurur."""
        self._timer.stop()
        self._running = False
        if self._overlay:
            self._overlay.hide()

        if self._dashboard:
            self._dashboard.set_running_state(False)

        logger.info("Çeviri durduruldu.")

    def resume(self) -> None:
        """Çeviri döngüsünü devam ettirir."""
        if self._region and self._overlay:
            if self._dashboard and hasattr(self._dashboard, "interval_spin"):
                self._interval = self._dashboard.interval_spin.value()
            self._timer.start(self._interval)
            self._running = True
            self._overlay.show()
            if self._dashboard:
                self._dashboard.set_running_state(True)
            logger.info("Çeviri devam ediyor.")

    # endregion

    # region Bölge Seçimi

    def change_region(self) -> None:
        """Bölge seçimini yeniden yapar."""
        was_running = self._running
        self.stop()

        # Dashboard'u geçici olarak gizle (seçim ekranı için temiz alan)
        if self._dashboard:
            self._dashboard.hide()

        region = select_region()

        if self._dashboard:
            self._dashboard.show()

        if region:
            self._region = region
            if self._overlay:
                self._overlay.update_region(region)
            logger.info("Yeni bölge seçildi: %s", self._region)

        if was_running:
            self.start()

    # endregion

    # region Ana Döngü

    def _tick(self) -> None:
        """Her zamanlayıcı tick'inde çalışır: yakala → OCR → çevir → göster."""
        if not self._region:
            return

        self._tick_count += 1

        try:
            image = capture_region(self._region)
            text = extract_text(image)

            if not text.strip():
                return

            if not self._cache.is_new_text(text):
                return

            logger.info("[#%d] OCR metin: '%s'", self._tick_count, text[:80])

            cached = self._cache.get_cached_translation(text)
            if cached:
                self._last_translation = cached
                if self._overlay:
                    self._overlay.update_text(cached)
                return

            translation = translate(text, model=self._model)
            if translation:
                self._last_translation = translation
                self._cache.store(text, translation)
                if self._overlay:
                    self._overlay.update_text(translation)
            else:
                if self._last_translation and self._overlay:
                    self._overlay.update_text(f"⚠ {self._last_translation}")

        except Exception as exc:
            logger.error("[#%d] Tick hatası: %s", self._tick_count, exc)

    # endregion


# region System Tray


def create_system_tray(app: QApplication, ocr_app: OCRTranslateApp) -> QSystemTrayIcon:
    """System tray ikonu ve menüsünü oluşturur."""
    tray = QSystemTrayIcon()

    # Basit ikon oluştur (metin tabanlı)
    from PyQt5.QtGui import QPixmap, QColor, QPainter, QFont

    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(0, 150, 255))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
    font = QFont("Sans", 22, QFont.Bold)
    painter.setFont(font)
    painter.setPen(QColor(255, 255, 255))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "TR")
    painter.end()
    tray.setIcon(QIcon(pixmap))

    menu = QMenu()

    action_dash = QAction("🏠 Dashboard")
    action_pause = QAction("⏸ Durdur")
    action_resume = QAction("▶ Devam Et")
    action_region = QAction("🔲 Bölge Değiştir")
    action_quit = QAction("❌ Çıkış")

    def on_dash() -> None:
        if ocr_app._dashboard:
            ocr_app._dashboard.show()
            ocr_app._dashboard.raise_()

    def on_pause() -> None:
        ocr_app.stop()

    def on_resume() -> None:
        ocr_app.resume()

    def on_region() -> None:
        ocr_app.change_region()

    def on_quit() -> None:
        ocr_app.stop()
        app.quit()

    action_dash.triggered.connect(on_dash)
    action_pause.triggered.connect(on_pause)
    action_resume.triggered.connect(on_resume)
    action_region.triggered.connect(on_region)
    action_quit.triggered.connect(on_quit)

    menu.addAction(action_dash)
    menu.addSeparator()
    menu.addAction(action_pause)
    menu.addAction(action_resume)
    menu.addSeparator()
    menu.addAction(action_region)
    menu.addSeparator()
    menu.addAction(action_quit)

    tray.setContextMenu(menu)
    tray.setToolTip("OCR-TRANSLATE")

    return tray


# endregion


# region CLI


def parse_args() -> argparse.Namespace:
    """Komut satırı argümanlarını ayrıştırır."""
    parser = argparse.ArgumentParser(
        description="OCR-TRANSLATE — Ekrandaki metni gerçek zamanlı çevir",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=config.OLLAMA_MODEL,
        help=f"Ollama modeli (varsayılan: {config.OLLAMA_MODEL})",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=config.CAPTURE_INTERVAL_MS,
        help=f"Yakalama aralığı ms (varsayılan: {config.CAPTURE_INTERVAL_MS})",
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="Tam ekran modunda başlat (bölge seçimi atlanır)",
    )
    return parser.parse_args()


# endregion


def main() -> None:
    """Uygulama giriş noktası."""
    args = parse_args()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    ocr_app = OCRTranslateApp(
        model=args.model,
        interval=args.interval,
        fullscreen=args.fullscreen,
    )

    # Dashboard ve Motoru Başlat
    ocr_app.run()

    # System tray
    tray = create_system_tray(app, ocr_app)
    tray.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
