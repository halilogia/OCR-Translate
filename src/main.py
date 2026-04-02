import argparse
import logging
import os
import signal
import sys
import time
import subprocess
import re
from typing import Optional

from PyQt5.QtCore import (
    QTimer,
    Qt,
    QSharedMemory,
    QThread,
    pyqtSignal,
    pyqtSlot,
    QObject,
)
from PyQt5.QtGui import QIcon, QPixmap, QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QMenu,
    QSystemTrayIcon,
    QMessageBox,
    QShortcut,
)
from PyQt5.QtDBus import QDBusInterface, QDBusReply, QDBusConnection, QDBusMessage

import config
from cache import TextCache
from ocr_engine import extract_text
from overlay import TranslationOverlay
from region_selector import select_region
from screen_capture import Region, capture_region, get_full_screen_region
from translator import check_ollama_connection, translate
from dashboard import MainDashboard
import storage
from i18n import _
from refiner import CognitiveRefiner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("OCR-TRANSLATE")


def _is_translation_noise(text: str) -> bool:
    """Çeviri çıktısındaki gürültüyü tespit eder."""
    cleaned = text.strip()
    if not cleaned:
        return True
    if len(cleaned) < 2:
        return True
    # Teknik sızıntı kontrolü
    noise_patterns = [
        "Task:",
        "Guidelines:",
        "Return ONLY",
        "DO NOT",
        "Sen profesyonel",
        "Görev:",
        "Kurallar:",
        "Metin:",
        "Atmosfer:",
        "Format:",
        "Translation:",
    ]
    u = cleaned.upper()
    if any(p.upper() in u for p in noise_patterns):
        return True
    # Sembol ağırlıklı gürültü
    alpha_count = sum(1 for c in cleaned if c.isalpha() or c.isspace())
    if len(cleaned) > 0 and alpha_count / len(cleaned) < 0.4:
        return True
    return False


def _global_log_to_console(
    tag: str, content: str, engine: str = "N/A", model: str = "N/A"
):
    """Merkezi loglama fonksiyonu. (AAA Global)."""
    log_path = os.path.join(os.getcwd(), config.CONSOLE_LOG_FILE)
    timestamp = time.strftime("%H:%M:%S")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            if tag == "PIPELINE":
                f.write(f"\n{'=' * 20} {timestamp} [PIPELINE] {'=' * 20}\n")
                f.write(f"[Engine: {engine.upper()}] | [Model: {model}]\n")
                f.write(content + "\n")  # Content already formatted
                f.write("-" * 50 + "\n")
            else:
                f.write(f"\n{'=' * 20} {timestamp} [{tag}] {'=' * 20}\n")
                f.write(f"[Engine: {engine.upper()}] | [Model: {model}]\n")
                f.write(content.strip() + "\n")
                f.write("-" * 50 + "\n")
    except Exception as e:
        logger.error(f"Global Log hatası: {e}")


class TranslationWorker(QThread):
    """
    Arka planda ekran yakalama, OCR ve çeviri işlemlerini yöneten thread.
    Ana arayüzün donmasını engeller. (AAA Performance)
    """

    result_ready = pyqtSignal(str)
    status_msg = pyqtSignal(str)
    capture_started = pyqtSignal()
    capture_finished = pyqtSignal()
    blocks_ready = pyqtSignal(list)  # List[TextBlock] Döndürür

    def __init__(
        self,
        model: str,
        engine_type: str,
        interval: int,
        region: Region,
        cache: TextCache,
        node_id: Optional[int] = None,
        uuid: Optional[str] = None,
    ):
        super().__init__()
        self.model = model
        self.engine_type = engine_type
        self.interval = interval
        self.region = region
        self.cache = cache
        self.node_id = node_id
        self.uuid = uuid
        self._running = True
        self._last_text = ""
        self.refiner = CognitiveRefiner()

    def stop(self):
        self._running = False

    def update_params(
        self,
        model: Optional[str] = None,
        engine_type: Optional[str] = None,
        interval: Optional[int] = None,
        region: Optional[Region] = None,
        node_id: Optional[int] = None,
        uuid: Optional[str] = None,
    ):
        if model:
            self.model = model
        if engine_type:
            self.engine_type = engine_type
        if interval:
            self.interval = interval
        if region:
            self.region = region
        if node_id:
            self.node_id = node_id
        if uuid:
            self.uuid = uuid

    def run(self):
        logger.info("Worker thread başladı.")
        empty_streak = 0
        from ocr_engine import (
            OCREngineFactory,
            merge_text_blocks,
            get_background_color,
            filter_ui_blocks,
            extract_text_from_bubbles,
        )

        engine = OCREngineFactory.get_engine(self.engine_type)

        while self._running:
            t_total = time.time()
            try:
                # 1. Ekran Yakala
                self.capture_started.emit()
                time.sleep(0.15)
                t_capture = time.time()
                image = capture_region(
                    self.region, node_id=self.node_id, uuid=self.uuid
                )
                t_capture_ms = (time.time() - t_capture) * 1000
                self.capture_finished.emit()

                # 2. OCR (Balon tespiti + UI filtreleme)
                t_ocr = time.time()

                # Balon tespiti etkinse önce balonları bul
                if getattr(config, "ENABLE_BUBBLE_DETECTION", False):
                    raw_blocks = extract_text_from_bubbles(image, engine)
                else:
                    raw_blocks = engine.extract_blocks(image)

                # UI gürültü filtreleme
                if getattr(config, "ENABLE_UI_FILTER", True):
                    raw_blocks = filter_ui_blocks(raw_blocks, image)

                t_ocr_ms = (time.time() - t_ocr) * 1000

                if not raw_blocks:
                    empty_streak += 1
                    if empty_streak == 5:
                        logger.warning("OCR ardışık 5 boş sonuç döndürdü.")
                    continue

                empty_streak = 0

                # 2b. Güven filtresi (düşük güvenli blokları ele)
                high_conf_blocks = [b for b in raw_blocks if b.conf >= 0.20]
                if not high_conf_blocks:
                    continue

                # 3. Merge
                t_merge = time.time()
                merged_blocks = merge_text_blocks(high_conf_blocks)
                t_merge_ms = (time.time() - t_merge) * 1000

                if not merged_blocks:
                    continue

                # 3b. Duplicate blok tespiti (aynı metin farklı blokta)
                seen_texts: set[str] = set()
                unique_blocks = []
                for b in merged_blocks:
                    normalized = b.text.strip().lower()
                    if normalized not in seen_texts and len(normalized) >= 2:
                        seen_texts.add(normalized)
                        unique_blocks.append(b)
                merged_blocks = unique_blocks

                if not merged_blocks:
                    continue

                # 4. Refine (OCR düzeltme)
                t_refine = time.time()
                if config.ENABLE_REFINER:
                    all_refined = [
                        self.refiner.refine(b.text, image) for b in merged_blocks
                    ]
                else:
                    all_refined = [b.text for b in merged_blocks]
                t_refine_ms = (time.time() - t_refine) * 1000

                # Boş refine sonuçlarını filtrele
                valid_pairs = [
                    (b, r) for b, r in zip(merged_blocks, all_refined) if r.strip()
                ]
                if not valid_pairs:
                    continue
                merged_blocks = [p[0] for p in valid_pairs]
                all_refined = [p[1] for p in valid_pairs]

                combined_text = "\n---\n".join(all_refined)

                # Cache kontrolü
                if not self.cache.is_new_text(combined_text):
                    continue

                # 5. Çeviri
                all_translated: list[str] = []
                cached = self.cache.get_cached_translation(combined_text)
                t_translate_ms = 0

                if cached:
                    all_translated = cached.split("\n---\n")
                    t_translate_ms = 0
                else:
                    prompt = (
                        "Aşağıdaki ayrı metin bloklarını Türkçe'ye çevir. "
                        "Sıralamayı ve '---' ayırıcısını koru. "
                        "Açıklama ekleme. Her blok ayrı satırda kalsın.\n\n"
                        f"{combined_text}"
                    )
                    t_translate = time.time()
                    translation = translate(prompt, model=self.model)
                    t_translate_ms = (time.time() - t_translate) * 1000
                    if translation:
                        self.cache.store(combined_text, translation)
                        all_translated = translation.split("\n---\n")
                    else:
                        logger.warning("Çeviri başarısız, orijinal metin kullanılıyor")
                        t_translate_ms = 0

                # Sonuçları bloklara geri işle
                translated_blocks = []
                for i, b in enumerate(merged_blocks):
                    txt = all_translated[i] if i < len(all_translated) else b.text
                    # Çeviri gürültü kontrolü
                    if _is_translation_noise(txt):
                        continue
                    bg = get_background_color(image, b.box)
                    translated_blocks.append(
                        {"text": txt.strip(), "box": b.box, "bg": bg}
                    )

                # Çıktı Üret
                if translated_blocks:
                    self.blocks_ready.emit(translated_blocks)
                    full_res = "\n".join([tb["text"] for tb in translated_blocks])
                    self.result_ready.emit(full_res)

                # Console log
                t_total_ms = (time.time() - t_total) * 1000
                cache_status = "HIT" if (cached and t_translate_ms == 0) else "MISS"
                timing = (
                    f"Timing: capture={t_capture_ms:.0f}ms | "
                    f"ocr={t_ocr_ms:.0f}ms | "
                    f"merge={t_merge_ms:.1f}ms | "
                    f"refine={t_refine_ms:.0f}ms | "
                    f"translate={t_translate_ms:.0f}ms | "
                    f"total={t_total_ms:.0f}ms\n"
                    f"Cache: {cache_status} | Raw: {len(raw_blocks)} → Filtered: {len(high_conf_blocks)} → Merged: {len(merged_blocks)} → Output: {len(translated_blocks)}"
                )

                log_lines = []
                log_idx = 1
                for i, tb in enumerate(translated_blocks):
                    src = all_refined[i] if i < len(all_refined) else "?"
                    if len(src.strip()) < 3:
                        continue
                    log_lines.append(f"  [{log_idx}] {src}\n       → {tb['text']}")
                    log_idx += 1

                if log_lines:
                    self._log_to_console_file(
                        "PIPELINE",
                        timing + "\n" + "\n".join(log_lines),
                    )
                else:
                    self._log_to_console_file("PIPELINE", timing)

            except Exception as e:
                logger.error(f"Worker hatası: {e}")
                self.status_msg.emit(f"Hata: {str(e)}")

            # Bekleme (Interval - İşlem Süresi)
            t_total_ms = (time.time() - t_total) * 1000
            wait_time = max(1, self.interval - t_total_ms)
            logger.debug(
                f"Frame süresi: {t_total_ms:.1f}ms, Bekleme: {wait_time:.1f}ms"
            )
            time.sleep(wait_time / 1000.0)

        logger.info("Worker thread durduruldu.")

    def _log_to_console_file(self, tag: str, content: str):
        """Worker üzerinden ana uygulamanın loglama metodunu çağırır."""
        # Not: Bu metodun ana uygulamada (OCRTranslateApp) olması daha mantıklı.
        # Şimdilik direkt dosya yazımını burada da yapabiliriz veya main referansı alabiliriz.
        # En temizi main.py içinde global bir helper.
        _global_log_to_console(tag, content, self.engine_type, self.model)


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

    @pyqtSlot(str)
    def _on_capture_method_changed(self, method: str) -> None:
        config.CAPTURE_METHOD = method
        storage.update_setting("capture_method", method)
        logger.info("Yakalama yöntemi değiştirildi: %s", method)
        # Worker global config'i (config.CAPTURE_METHOD) her döngüde kontrol edecek.

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
        # self._worker.status_msg.connect(self._on_status_msg) # _on_status_msg is not defined in the provided context

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
                    _global_log_to_console("WINDOW-PICK", msg)

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
                    err = _("picking_window_err")  # JSON'a eklenmeli
                    logger.warning(err)
                    print(f"\033[91mDEBUG DBUS RAW:\033[0m\n{result.stdout}")
                    _global_log_to_console(
                        "WINDOW-PICK-ERR", f"{err}\nRAW: {result.stdout}"
                    )
            else:
                err = f"DBus hatası: {result.stderr}"
                logger.error(err)
                _global_log_to_console("WINDOW-PICK-ERR", err)
        except Exception as e:
            err = f"Pencere seçimi sistem hatası: {e}"
            logger.error(err)
            _global_log_to_console("WINDOW-PICK-ERR", err)

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
                        self._worker.update_params(region=curr)
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
        _global_log_to_console("AURA-READY", f"Pipewire Stream ID: {node_id}")

    def quit_app(self) -> None:
        """Uygulamayı tamamen ve güvenli bir şekilde kapatır."""
        logger.info("Uygulama kapatılıyor...")
        self.stop()
        if self._worker:
            self._worker.wait(2000)
        # Kilit dosyasını bırak
        if hasattr(self, "_shared_mem"):
            self._shared_mem.detach()
        QApplication.quit()
        sys.exit(0)


def create_system_tray(app: QApplication, ocr_app: OCRTranslateApp) -> QSystemTrayIcon:
    tray = QSystemTrayIcon()
    logo_path = os.path.join(os.getcwd(), "assets/logo.png")
    if os.path.exists(logo_path):
        tray.setIcon(QIcon(logo_path))
    else:
        pix = QPixmap(64, 64)
        pix.fill(Qt.transparent)
        tray.setIcon(QIcon(pix))

    menu = QMenu()
    menu.setStyleSheet(
        "QMenu { background: #16161B; color: white; border: 1px solid #333; }"
    )
    act_dash = QAction("🏠 " + _("tray_restore"), menu)
    act_dash.triggered.connect(
        lambda: ocr_app._dashboard.show() or ocr_app._dashboard.raise_()
    )
    act_pause = QAction("⏸ " + _("tray_pause"), menu)
    act_pause.triggered.connect(ocr_app.stop)
    act_resume = QAction("▶ " + _("tray_resume"), menu)
    act_resume.triggered.connect(ocr_app.resume)
    act_quit = QAction("❌ " + _("tray_exit"), menu)
    act_quit.triggered.connect(ocr_app.quit_app)
    menu.addAction(act_dash)
    menu.addSeparator()
    menu.addAction(act_pause)
    menu.addAction(act_resume)
    menu.addSeparator()
    menu.addAction(act_quit)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda r: ocr_app._dashboard.show() if r == QSystemTrayIcon.Trigger else None
    )
    return tray


def main() -> None:
    # Terminal log dosyasını oluştur ve yönlendir
    terminal_log_path = os.path.join(os.getcwd(), "terminal.log")
    try:
        # Dosyayı sıfırla
        with open(terminal_log_path, "w", encoding="utf-8") as f:
            f.write(
                f"=== {time.strftime('%Y-%m-%d %H:%M:%S')} TERMINAL LOG BAŞLADI ===\n\n"
            )

        # Tüm logging çıktısını dosyaya yönlendir
        file_handler = logging.FileHandler(terminal_log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"
            )
        )

        # Root logger'a ekle
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)

        # Stdout/stderr'i de dosyaya yönlendir
        class TeeOutput:
            def __init__(self, original, file):
                self.original = original
                self.file = file

            def write(self, text):
                self.original.write(text)
                self.original.flush()
                try:
                    self.file.write(text)
                    self.file.flush()
                except:
                    pass

            def flush(self):
                self.original.flush()
                try:
                    self.file.flush()
                except:
                    pass

        log_file = open(terminal_log_path, "a", encoding="utf-8")
        sys.stdout = TeeOutput(sys.__stdout__, log_file)
        sys.stderr = TeeOutput(sys.__stderr__, log_file)

    except Exception as e:
        print(f"Terminal log oluşturulamadı: {e}")

    # Uygulama Başlangıcında Console Log Dosyasını Temizle
    log_path = os.path.join(os.getcwd(), config.CONSOLE_LOG_FILE)
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(
                f"=== {time.strftime('%Y-%m-%d %H:%M:%S')} OCR-TRANSLATE LOG BAŞLADI ===\n"
            )
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    shared_mem = QSharedMemory("OCR_TRANSLATE_LOCK")
    if not shared_mem.create(1):
        shared_mem.attach()
        shared_mem.detach()
        if not shared_mem.create(1):
            logger.warning(_("already_running_msg"))
            sys.exit(0)

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None)
    parser.add_argument("--interval", type=int, default=None)
    parser.add_argument("--fullscreen", action="store_true")
    args = parser.parse_args()

    ocr_app = OCRTranslateApp(args.model, args.interval, args.fullscreen)
    ocr_app._shared_mem = shared_mem
    ocr_app.run()
    tray = create_system_tray(app, ocr_app)
    tray.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
