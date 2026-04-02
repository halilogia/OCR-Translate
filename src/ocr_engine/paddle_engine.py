"""
OCR-TRANSLATE — PaddleOCR Engine
Çok dilli, hızlı ve doğru OCR. Stylized fontlarda ve karmaşık layout'larda çok iyi.
"""

import logging
from typing import List

import cv2
import numpy as np

from config import OCR_LANG

from .base import OCREngine, TextBlock, _MIN_CONF_SCORE
from .utils import _ensure_min_size, _is_block_noise

logger = logging.getLogger(__name__)

_paddle_ocr_instance = None
_torch_loaded = False


class PaddleOCREngine(OCREngine):
    """
    PaddleOCR: Çok dilli, hızlı ve doğru OCR.
    Stylized fontlarda ve karmaşık layout'larda çok iyi.
    pip install paddleocr paddlepaddle
    """

    def __init__(self) -> None:
        global _paddle_ocr_instance
        logger.info("PaddleOCREngine başlatılıyor...")
        try:
            from paddleocr import PaddleOCR

            if _paddle_ocr_instance is None:
                # use_angle_cls: Eğik metin tespiti
                # lang: 'en' İngilizce, 'ch' Çince, 'japan' Japonca, 'korean' Korece
                lang = "en" if OCR_LANG == "eng" else OCR_LANG
                _paddle_ocr_instance = PaddleOCR(
                    use_angle_cls=True,
                    lang=lang,
                    show_log=False,
                    use_gpu=_torch_loaded,
                )
            self._ocr = _paddle_ocr_instance
            logger.info("PaddleOCR başarıyla yüklendi (lang=%s)", lang)
        except ImportError:
            logger.error("paddleocr yüklü değil! pip install paddleocr paddlepaddle")
            self._ocr = None

    def extract_blocks(self, image: np.ndarray) -> List[TextBlock]:
        if self._ocr is None:
            logger.warning("PaddleOCR kullanılamıyor, EasyOCR'a düşülüyor")
            from .easyocr_engine import EasyOCREngine

            return EasyOCREngine().extract_blocks(image)

        try:
            processed = self._preprocess(image)
            result = self._ocr.ocr(processed, cls=True)

            if not result or not result[0]:
                return []

            blocks = []
            for line in result[0]:
                bbox, (text, conf) = line
                text = text.strip()

                if not text or conf < _MIN_CONF_SCORE:
                    continue
                if _is_block_noise(text):
                    continue

                # PaddleOCR bbox: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                x = int(min(p[0] for p in bbox))
                y = int(min(p[1] for p in bbox))
                w = int(max(p[0] for p in bbox) - x)
                h = int(max(p[1] for p in bbox) - y)

                blocks.append(TextBlock(text=text, box=[x, y, w, h], conf=conf))

            return blocks
        except Exception as e:
            logger.error("PaddleOCR hatası: %s", e)
            return []

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """PaddleOCR için optimize edilmiş ön işleme."""
        scaled = _ensure_min_size(image, target_width=1200)
        # Hafif denoising (PaddleOCR kendi içinde de işliyor)
        try:
            denoised = cv2.fastNlMeansDenoisingColored(scaled, None, 6, 6, 7, 21)
        except Exception:
            denoised = scaled
        return denoised
