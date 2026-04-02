"""
OCR-TRANSLATE — Base OCR Engine Interface
Tüm OCR motorları için temel arayüz ve veri yapıları.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


# region VERİ YAPILARI
@dataclass
class TextBlock:
    """Metin içeriğini, koordinatlarını ve güven skorunu tutan yapı."""

    text: str
    box: List[int]  # [x, y, w, h]  (Orijinal görüntü üzerindeki koordinatlar)
    conf: float


# endregion

# region YAPILANDIRMA VE EŞİKLER
_MIN_CONF_SCORE = (
    0.40  # Tesseract için minimum güven eşiği (daha yüksek = daha az noise)
)
_GARBAGE_RATIO_THRESHOLD = 0.6
_MIN_TEXT_LENGTH = 2
_TARGET_MIN_WIDTH = 1000
# endregion


class OCREngine(ABC):
    """Tüm OCR motorları için temel arayüz."""

    @abstractmethod
    def extract_blocks(self, image: np.ndarray) -> List[TextBlock]:
        """Görüntüden metin bloklarını ve koordinatlarını çıkarır."""
        pass

    def extract_text(self, image: np.ndarray) -> str:
        """Geriye dönük uyumluluk: Tüm blokları tek bir metin olarak birleştirir."""
        blocks = self.extract_blocks(image)
        return " ".join([b.text for b in blocks]).strip()
