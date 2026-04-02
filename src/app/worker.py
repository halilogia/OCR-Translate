import logging
import time
from typing import Optional
from PyQt5.QtCore import QThread, pyqtSignal

import config
from cache import TextCache
from screen_capture import Region, capture_region
from translator import translate
from refiner import CognitiveRefiner
from ocr_engine import (
    OCREngineFactory,
    merge_text_blocks,
    get_background_color,
    filter_ui_blocks,
    extract_text_from_bubbles,
)
from utils.noise_filter import is_translation_noise
from utils.logger import global_log_to_console
import cv2
import numpy as np

logger = logging.getLogger("OCR-TRANSLATE.Worker")


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
        self._last_frame: Optional[np.ndarray] = None
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
        engine = OCREngineFactory.get_engine(self.engine_type)

        while self._running:
            t_total = time.time()
            try:
                # 1. Ekran Yakala
                self.capture_started.emit()
                # time.sleep(0.15) # Gereksiz gecikme kaldırıldı (AAA Speed)
                t_capture = time.time()
                image = capture_region(
                    self.region, node_id=self.node_id, uuid=self.uuid
                )
                t_capture_ms = (time.time() - t_capture) * 1000
                self.capture_finished.emit()

                # 1b. Static Frame Detection (Diff-Check)
                if self._last_frame is not None:
                    # Görüntüler arası farkı hesapla (MSE veya Structural Similarity)
                    # Hızlılık için resize edip farka bakıyoruz
                    prev_small = cv2.resize(self._last_frame, (100, 100))
                    curr_small = cv2.resize(image, (100, 100))
                    diff = cv2.absdiff(prev_small, curr_small)
                    mean_diff = np.mean(diff)

                    if mean_diff < 0.3:  # Eşik değeri düşürüldü (0.5 -> 0.3)
                        logger.debug(
                            f"Statik kare tespit edildi (diff={mean_diff:.3f}), atlanıyor."
                        )
                        t_total_ms = (time.time() - t_total) * 1000
                        wait_time = max(1, self.interval - t_total_ms)
                        time.sleep(wait_time / 1000.0)
                        continue

                self._last_frame = image.copy()

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
                    if is_translation_noise(txt):
                        continue
                    bg = get_background_color(image, b.box)
                    translated_blocks.append(
                        {
                            "text": txt.strip(),
                            "src_text": b.text.strip(),
                            "box": b.box,
                            "bg": bg,
                        }
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
        global_log_to_console(tag, content, self.engine_type, self.model)
