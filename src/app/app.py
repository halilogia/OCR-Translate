import logging
import os
import sys
import subprocess
import re
from typing import Optional

from PyQt5.QtCore import (
    QTimer,
    QSharedMemory,
    pyqtSlot,
    QObject,
)
from PyQt5.QtWidgets import (
    QApplication,
    QShortcut,
)
from PyQt5.QtGui import QKeySequence
from PyQt5.QtDBus import QDBusInterface, QDBusConnection, QDBusMessage

import config
import storage
from i18n import _
from cache import TextCache
from overlay import TranslationOverlay
from region_selector import select_region
from screen_capture import Region, get_full_screen_region
from dashboard import MainDashboard
from app.worker import TranslationWorker
from utils.logger import global_log_to_console

logger = logging.getLogger("OCR-TRANSLATE.App")


class OCRTranslateApp(QObject):
    """Ana uygulama sınıfı. Tüm bileşenleri orkestre eder."""

    def __init__(self, model: str, interval: int, fullscreen: bool) -> None:
        super().__init__()
        settings = storage.load_settings()
        config.OCR_ENGINE_TYPE = settings.get("ocr_engine_type", "easyocr")
        config.OVERLAY_MODE = settings.get("overlay_mode", "bottom")
        config.VISION_MODEL = settings.get("vision_model", "glm-ocr")

        self._fullscreen = fullscreen
        self._model = model if model else settings.get("model", config.OLLAMA_MODEL)
        self._interval = (
            interval
            if interval
            else settings.get("interval", config.CAPTURE_INTERVAL_MS)
        )

        self._region: Optional[Region] = None
        self._tracking_uuid: Optional[str] = None
        self._tracking_timer = QTimer()
        self._tracking_timer.timeout.connect(self._update_window_tracking)
        self._tracking_timer.setInterval(2000)  # 2 saniyede bir pencereyi kontrol et

        self._overlay: Optional[TranslationOverlay] = None
        self._dashboard: Optional[MainDashboard] = None
        self._worker: Optional[TranslationWorker] = None
        self._cache = TextCache()
        self._shared_mem: Optional[QSharedMemory] = None

        # Aura Background Engine (AAA Component)
        try:
            from aura_engine import AuraPipewireEngine

            self._aura_engine = AuraPipewireEngine()
            self._aura_engine.node_ready.connect(self._on_aura_node_ready)
            self._aura_engine.error_occurred.connect(
                lambda err: logger.error(f"Aura Hatası: {err}")
            )
        except ImportError:
            self._aura_engine = None
            logger.warning("aura_engine.py bulunamadı, Aura modu devre dışı.")

        self._aura_node_id: Optional[int] = None

    def run(self) -> None:
        """Dashboard'u başlatır ve uygulamayı hazır hale getirir."""
        self._dashboard = MainDashboard(self._model, self._interval)
        self._dashboard.show()

        # Dashboard sinyallerini bağla
        self._dashboard.start_requested.connect(self.start)
        self._dashboard.stop_requested.connect(self.stop)
        self._dashboard.region_change_requested.connect(self.change_region)
        self._dashboard.window_selection_requested.connect(self.change_window_region)
        self._dashboard.model_changed.connect(self._on_model_changed)
        self._dashboard.vision_combo.currentTextChanged.connect(
            self._on_vision_model_changed
        )
        self._dashboard.engine_changed.connect(self._on_engine_changed)
        self._dashboard.overlay_mode_changed.connect(self._on_overlay_mode_changed)
        self._dashboard.capture_method_changed.connect(self._on_capture_method_changed)
        self._dashboard.interval_changed.connect(self._on_interval_changed)
        self._dashboard.show_source_changed.connect(self._on_show_source_changed)
        self._dashboard.exit_requested.connect(self.quit_app)

        # Klavye Kısayolları
        self._setup_shortcuts()

        if self._fullscreen:
            self.start()

    def _setup_shortcuts(self) -> None:
        """Klavye kısayollarını dashboard'a bağlar."""
        if not self._dashboard:
            return

        # F5: Çeviriyi Başlat / Durdur
        sc_toggle = QShortcut(QKeySequence("F5"), self._dashboard)
        sc_toggle.activated.connect(self._on_toggle_shortcut)

        # F6: Alan Seç
        sc_region = QShortcut(QKeySequence("F6"), self._dashboard)
        sc_region.activated.connect(self.change_region)

        # F7: Pencere Seç
        sc_window = QShortcut(QKeySequence("F7"), self._dashboard)
        sc_window.activated.connect(self.change_window_region)

        # Escape: Çeviriyi Durdur
        sc_stop = QShortcut(QKeySequence("Escape"), self._dashboard)
        sc_stop.activated.connect(self.stop)

        # F8: Dashboard'u Göster/Gizle
        sc_toggle_dash = QShortcut(QKeySequence("F8"), self._dashboard)
        sc_toggle_dash.activated.connect(self._toggle_dashboard)

        logger.info("Klavye kısayolları kaydedildi: F5, F6, F7, F8, Escape")

    def _on_toggle_shortcut(self) -> None:
        """F5 kısayolu: Çalışıyorsa durdur, duruyorsa başlat."""
        if self._worker and self._worker.isRunning():
            self.stop()
        else:
            self.start()

    def _toggle_dashboard(self) -> None:
        """F8 kısayolu: Dashboard'u göster/gizle."""
        if self._dashboard:
            if self._dashboard.isVisible():
                self._dashboard.hide()
            else:
                self._dashboard.show()
                self._dashboard.raise_()

    def _on_model_changed(self, model: str) -> None:
        self._model = model
        storage.update_setting("model", model)
        if self._worker:
            self._worker.update_params(model=model)
        logger.info("Aktif model değiştirildi: %s", model)

    def _on_engine_changed(self, engine_type: str) -> None:
        config.OCR_ENGINE_TYPE = engine_type
        storage.update_setting("ocr_engine_type", engine_type)
        if self._worker:
            self._worker.update_params(engine_type=engine_type)
        logger.info("Aktif OCR motoru değiştirildi: %s", engine_type)

    def _on_vision_model_changed(self, model: str) -> None:
        config.VISION_MODEL = model
        storage.update_setting("vision_model", model)
        logger.info("Vision OCR modeli değiştirildi: %s", model)

    def _on_overlay_mode_changed(self, mode: str) -> None:
        config.OVERLAY_MODE = mode
        storage.update_setting("overlay_mode", mode)
        if self._overlay:
            self._overlay.update()  # Pencere geometrisi bir sonraki güncellemede düzelecek
        logger.info("Overlay modu değiştirildi: %s", mode)

    def _on_interval_changed(self, interval: int) -> None:
        self._interval = interval
        storage.update_setting("interval", interval)
        if self._worker:
            self._worker.update_params(interval=interval)
        logger.info("Tarama aralığı değiştirildi: %dms", interval)

    def _on_show_source_changed(self, show: bool) -> None:
        config.SHOW_SOURCE_TEXT = show
        storage.update_setting("show_source_text", show)
        logger.info("Orijinal metin gösterimi: %s", show)

    @pyqtSlot(str)
    def _on_capture_method_changed(self, method: str) -> None:
        config.CAPTURE_METHOD = method
        storage.update_setting("capture_method", method)
        logger.info("Yakalama yöntemi değiştirildi: %s", method)

    def start(self) -> bool:
        # AAA Stability Guard: Zaten çalışıyorsa ve bölge değişmediyse yeniden başlatma
        if self._worker and self._worker.isRunning():
            logger.info("OCR-TRANSLATE zaten aktif, yeniden başlatma atlanıyor.")
            return True

        logger.info("OCR-TRANSLATE başlatılıyor...")

        # UI'dan güncel interval değerini oku (Force Read)
        if self._dashboard:
            self._interval = self._dashboard.interval_spin.value()
            logger.info(
                "CRITICAL: Başlatma sırasında UI'dan okunan interval: %dms",
                self._interval,
            )

        if self._region is None:
            if self._fullscreen:
                self._region = get_full_screen_region()
            else:
                self._region = select_region()
                if self._region is None:
                    return False

        if self._overlay is None:
            self._overlay = TranslationOverlay(self._region)
        else:
            self._overlay.update_region(self._region)

        self._overlay.update_text("\u23f3 " + _("ready_loading"))
        self._overlay.show()

        # Worker Başlat
        if self._worker:
            self._worker.stop()
            self._worker.wait()

        self._worker = TranslationWorker(
            self._model,
            config.OCR_ENGINE_TYPE,
            self._interval,
            self._region,
            self._cache,
            node_id=self._aura_node_id,
            uuid=self._tracking_uuid,
        )
        self._worker.result_ready.connect(self._overlay.update_text)
        if hasattr(self._overlay, "update_blocks"):
            self._worker.blocks_ready.connect(self._overlay.update_blocks)

        # Yakalama sızdırmazlığı (AAA Stealth Mode)
        if self._dashboard:
            self._worker.capture_started.connect(
                lambda: self._dashboard.set_capture_mode(True)
            )
            self._worker.capture_finished.connect(
                lambda: self._dashboard.set_capture_mode(False)
            )

        self._worker.start()

        if self._dashboard:
            self._dashboard.set_running_state(True)
            # Çeviri başladığında dashboard'u gizle (sistem tepsisine iner)
            self._dashboard.hide()
        return True

    def stop(self) -> None:
        if self._worker:
            self._worker.stop()
        if self._overlay:
            self._overlay.hide()
        if self._dashboard:
            self._dashboard.set_running_state(False)
            self._dashboard.show()
        self._tracking_timer.stop()
        logger.info("Çeviri durduruldu.")

    def resume(self) -> None:
        if self._region and self._overlay:
            self.start()

    def change_region(self) -> None:
        was_running = self._worker and self._worker.isRunning()
        self.stop()
        if self._dashboard:
            self._dashboard.hide()
        region = select_region()
        if self._dashboard:
            self._dashboard.show()
        if region:
            self._region = region
            if self._overlay:
                self._overlay.update_region(region)
            if self._worker:
                self._worker.update_params(region=region)
        if was_running:
            self.start()

    def change_window_region(self) -> None:
        """KDE DBus üzerinden tıklanan pencerenin bölgesini seçer."""
        was_running = self._worker and self._worker.isRunning()
        self.stop()

        if self._dashboard:
            self._dashboard.hide()

        logger.info("Pencere seçimi bekleniyor (KDE DBus)...")
        try:
            cmd = [
                "dbus-send",
                "--session",
                "--print-reply",
                "--dest=org.kde.KWin",
                "/KWin",
                "org.kde.KWin.queryWindowInfo",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                # Regex ile koordinatları ayıkla (AAA Parsing - Double & UUID Support)
                x = re.search(
                    r'string "x"\s+variant\s+double\s+([-+]?[\d.]+)', result.stdout
                )
                y = re.search(
                    r'string "y"\s+variant\s+double\s+([-+]?[\d.]+)', result.stdout
                )
                w = re.search(
                    r'string "width"\s+variant\s+double\s+([\d.]+)', result.stdout
                )
                h = re.search(
                    r'string "height"\s+variant\s+double\s+([\d.]+)', result.stdout
                )
                uuid = re.search(
                    r'string "uuid"\s+variant\s+string\s+"([^"]+)"', result.stdout
                )
                caption = re.search(
                    r'string "caption"\s+variant\s+string\s+"([^"]+)"', result.stdout
                )
                res_class = re.search(
                    r'string "resourceClass"\s+variant\s+string\s+"([^"]+)"',
                    result.stdout,
                )

                if all([x, y, w, h]):
                    region = {
                        "left": int(float(x.group(1))),
                        "top": int(float(y.group(1))),
                        "width": int(float(w.group(1))),
                        "height": int(float(h.group(1))),
                    }
                    self._tracking_uuid = uuid.group(1) if uuid else None
                    target_name = (
                        caption.group(1)
                        if caption
                        else (res_class.group(1) if res_class else "Unknown")
                    )

                    msg = f"{_('window_picked')} ({target_name}): {region}"
                    logger.info(msg)
                    global_log_to_console("WINDOW-PICK", msg)

                    self._region = region
                    if self._dashboard:
                        self._dashboard.set_target_name(target_name)
                    if self._overlay:
                        self._overlay.update_region(region)
                    if self._worker:
                        self._worker.update_params(
                            region=region, uuid=self._tracking_uuid
                        )

                    # Takibi başlat
                    if self._tracking_uuid:
                        self._tracking_timer.start()

                    # Aura Engine (Pipewire) Handshake Başlat (AAA Feature)
                    if self._aura_engine:
                        self._aura_engine.start_aura()
                else:
                    err = _("picking_window_err")
                    logger.warning(err)
                    print(f"\033[91mDEBUG DBUS RAW:\033[0m\n{result.stdout}")
                    global_log_to_console(
                        "WINDOW-PICK-ERR", f"{err}\nRAW: {result.stdout}"
                    )
            else:
                err = f"DBus hatası: {result.stderr}"
                logger.error(err)
                global_log_to_console("WINDOW-PICK-ERR", err)
        except Exception as e:
            err = f"Pencere seçimi sistem hatası: {e}"
            logger.error(err)
            global_log_to_console("WINDOW-PICK-ERR", err)

        if self._dashboard:
            self._dashboard.show()
        if was_running:
            self.start()

    def _update_window_tracking(self):
        """Pencere pozisyonunu takip eder ve gerekirse bölgeyi günceller. (Aura Tracking - QtDBus)."""
        if not self._tracking_uuid:
            self._tracking_timer.stop()
            return

        try:
            # AAA Implementation: QtDBus ile doğrudan ve hızlı sorgu
            iface = QDBusInterface(
                "org.kde.KWin", "/KWin", "org.kde.KWin", QDBusConnection.sessionBus()
            )
            reply = iface.call("getWindowInfo", self._tracking_uuid)

            if reply.type() == QDBusMessage.ReplyMessage:
                results = reply.arguments()[0]

                # KDE 6: x, y, width, height (double)
                x = results.get("x", 0.0)
                y = results.get("y", 0.0)
                w = results.get("width", 0.0)
                h = results.get("height", 0.0)

                curr = {
                    "left": int(float(x)),
                    "top": int(float(y)),
                    "width": int(float(w)),
                    "height": int(float(h)),
                }

                # Eğer pozisyon veya boyut değiştiyse güncelle
                if self._region != curr:
                    logger.info(
                        f"Pencere takibi (Aura): Pozisyon güncellendi -> {curr}"
                    )
                    self._region = curr
                    if self._overlay:
                        self._overlay.update_region(curr)
                    if self._worker:
                        self._worker.update_params(
                            region=curr, uuid=self._tracking_uuid
                        )
            else:
                # Pencere muhtemelen kapandı veya UUID geçersiz
                logger.warning(
                    f"Takip edilen pencere bulunamadı (UUID: {self._tracking_uuid})."
                )
                self._tracking_timer.stop()
                self._tracking_uuid = None
        except Exception as e:
            logger.error(f"QtDBus Takip Hatası: {e}")

    def _on_aura_node_ready(self, node_id: int):
        """Pipewire stream hazır olduğunda çağrılır."""
        logger.info(f"Aura: Pipewire Stream Aktif! Node ID: {node_id}")
        self._aura_node_id = node_id
        if self._worker:
            self._worker.update_params(node_id=node_id)
        global_log_to_console("AURA-READY", f"Pipewire Stream ID: {node_id}")

    def quit_app(self) -> None:
        """Uygulamayı tamamen ve güvenli bir şekilde kapatır."""
        logger.info("Uygulama kapatılıyor...")
        self.stop()
        if self._worker:
            self._worker.wait(2000)
        # Kilit dosyasını bırak
        if self._shared_mem:
            self._shared_mem.detach()
        QApplication.quit()
        sys.exit(0)
