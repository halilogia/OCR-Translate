"""
OCR-TRANSLATE — Manga OCR Engine
Japonca manga için özelleştirilmiş en iyi OCR.
HYBRID MODE: EasyOCR ile koordinat tespiti + MangaOCR ile metin okuma.
"""

import logging
from typing import List

import cv2
import numpy as np

from .base import OCREngine, TextBlock
from .utils import _is_garbage

logger = logging.getLogger(__name__)

_manga_ocr_instance = None


class MangaOCREngine(OCREngine):
    """
    Manga-OCR: Japonca manga için özelleştirilmiş en iyi OCR.
    Kana, Kanji ve stylized fontlarda mükemmel sonuç verir.

    HYBRID MODE: EasyOCR ile koordinat tespiti + MangaOCR ile metin okuma
    Bu sayede hem doğru koordinatlar hem de doğru Japonca metin elde edilir.

    pip install manga-ocr
    """

    def __init__(self) -> None:
        global _manga_ocr_instance
        logger.info("MangaOCREngine başlatılıyor...")
        try:
            from manga_ocr import MangaOcr

            if _manga_ocr_instance is None:
                _manga_ocr_instance = MangaOcr()
            self._ocr = _manga_ocr_instance
            logger.info("MangaOCR başarıyla yüklendi")
        except ImportError:
            logger.error("manga-ocr yüklü değil! pip install manga-ocr")
            self._ocr = None

        # Koordinat tespiti için EasyOCR (Hybrid Mode)
        self._coord_detector = None

    def _get_coord_detector(self):
        """Lazy-load koordinat dedektörü (EasyOCR)"""
        if self._coord_detector is None:
            from .easyocr_engine import EasyOCREngine

            self._coord_detector = EasyOCREngine()
        return self._coord_detector

    def extract_blocks(self, image: np.ndarray) -> List[TextBlock]:
        """
        HYBRID MODE:
        1. EasyOCR ile metin bölgelerinin koordinatlarını tespit et
        2. Her bölgeyi MangaOCR ile oku (daha doğru Japonca)
        """
        if self._ocr is None:
            logger.warning("MangaOCR yok, sadece EasyOCR kullanılıyor")
            return self._get_coord_detector().extract_blocks(image)

        # 1. EasyOCR ile koordinatları al
        coord_blocks = self._get_coord_detector().extract_blocks(image)

        if not coord_blocks:
            # Fallback: Tüm görüntüyü tek blok olarak işle
            text = self.extract_text(image)
            if text:
                h, w = image.shape[:2]
                return [TextBlock(text=text, box=[0, 0, w, h], conf=0.95)]
            return []

        # 2. Her blok için MangaOCR ile metni oku
        result_blocks = []
        for block in coord_blocks:
            x, y, w, h = block.box
            # Blok bölgesini kırp (padding ekle)
            pad = 5
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(image.shape[1], x + w + pad)
            y2 = min(image.shape[0], y + h + pad)

            cropped = image[y1:y2, x1:x2]

            if cropped.size == 0:
                continue

            # MangaOCR ile oku
            manga_text = self._extract_text_from_crop(cropped)

            if manga_text:
                result_blocks.append(
                    TextBlock(
                        text=manga_text,
                        box=[x, y, w, h],  # Orijinal koordinatlar
                        conf=0.95,
                    )
                )
                logger.info(
                    f"[OCR-Manga-Hybrid] Block ({x},{y},{w},{h}): '{manga_text[:50]}'"
                )
            else:
                # MangaOCR başarısız olursa EasyOCR sonucunu kullan
                if block.text:
                    result_blocks.append(block)

        return result_blocks

    def _extract_text_from_crop(self, cropped: np.ndarray) -> str:
        """Kırpılmış görüntüden MangaOCR ile metin çıkar."""
        try:
            from PIL import Image

            if len(cropped.shape) == 2:
                pil_img = Image.fromarray(cropped)
            else:
                pil_img = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))

            text = self._ocr(pil_img)
            if text and not _is_garbage(text):
                return text.strip()
            return ""
        except Exception as e:
            logger.error("MangaOCR crop hatası: %s", e)
            return ""

    def extract_text(self, image: np.ndarray) -> str:
        """Tüm görüntüden tek metin çıkar (legacy)."""
        if self._ocr is None:
            logger.warning("MangaOCR kullanılamıyor, EasyOCR'a düşülüyor")
            return self._get_coord_detector().extract_text(image)

        try:
            from PIL import Image

            if len(image.shape) == 2:
                pil_img = Image.fromarray(image)
            else:
                pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

            text = self._ocr(pil_img)
            if text and not _is_garbage(text):
                logger.info("[OCR-Manga] Başarılı: '%s'", text[:100])
                return text.strip()
            return ""
        except Exception as e:
            logger.error("MangaOCR hatası: %s", e)
            return ""
