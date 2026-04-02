"""
OCR-TRANSLATE — OCR Engine Factory
Motor seçimini yöneten fabrika sınıfı.
"""

import logging
from typing import List, Optional

import config

from .base import OCREngine

logger = logging.getLogger(__name__)


class OCREngineFactory:
    """Motor seçimini yöneten fabrika sınıfı."""

    _instances = {}

    @classmethod
    def get_engine(cls, engine_type: Optional[str] = None) -> OCREngine:
        if engine_type is None:
            engine_type = config.OCR_ENGINE_TYPE

        # Otomatik Seçim Mantığı (AAA Auto-Selection)
        if engine_type == "auto":
            import shutil

            # 1. Tesseract (Hız önceliği - sistemde kurulu mu?)
            if shutil.which("tesseract"):
                engine_type = "tesseract"
            # 2. EasyOCR (Doğruluk/Font önceliği - default)
            else:
                engine_type = "easyocr"
            logger.info(
                f"OCR Auto-Select: Sisteme en uygun motor seçildi -> {engine_type}"
            )

        if engine_type not in cls._instances:
            if engine_type == "tesseract":
                from .tesseract_engine import TesseractEngine

                cls._instances[engine_type] = TesseractEngine()
            elif engine_type == "vision":
                from .vision_engine import VisionLLMEngine

                cls._instances[engine_type] = VisionLLMEngine()
            elif engine_type == "manga":
                from .manga_engine import MangaOCREngine

                cls._instances[engine_type] = MangaOCREngine()
            elif engine_type == "paddle":
                from .paddle_engine import PaddleOCREngine

                cls._instances[engine_type] = PaddleOCREngine()
            else:
                from .easyocr_engine import EasyOCREngine

                cls._instances[engine_type] = EasyOCREngine()
        return cls._instances[engine_type]

    @classmethod
    def available_engines(cls) -> List[str]:
        """Kullanılabilir OCR motorlarını listeler."""
        engines = ["easyocr", "tesseract", "vision"]
        try:
            from manga_ocr import MangaOcr

            engines.append("manga")
        except ImportError:
            pass
        try:
            from paddleocr import PaddleOCR

            engines.append("paddle")
        except ImportError:
            pass
        return engines
