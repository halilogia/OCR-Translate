"""
OCR-TRANSLATE — OCR Engine Package
Modüler OCR motoru yapısı.
"""

import pytesseract

from .base import TextBlock, OCREngine
from .factory import OCREngineFactory
from .utils import (
    merge_text_blocks,
    get_background_color,
    is_ui_region,
    filter_ui_blocks,
    _ensure_min_size,
    _is_garbage,
    _is_block_noise,
    _deskew,
    _morphological_cleanup,
)
from .bubble_detection import (
    detect_speech_bubbles,
    extract_bubble_regions,
    extract_text_from_bubbles
)

# Geriye dönük uyumluluk için ana giriş noktası
def extract_text(image):
    """Geriye dönük uyumluluk: paket seviyesinden Tesseract ile metin çıkarır."""
    try:
        from config import OCR_LANG, OCR_PSM

        config_str = f"--oem 3 --psm {OCR_PSM} -l {OCR_LANG}"
        data = pytesseract.image_to_data(
            image, config=config_str, output_type=pytesseract.Output.DICT
        )

        words = []
        for text, conf in zip(data.get("text", []), data.get("conf", [])):
            t = str(text).strip()
            if not t:
                continue
            try:
                c = float(conf) / 100.0
            except Exception:
                c = 0.0
            if c >= 0.40:
                words.append(t)

        return " ".join(words).strip()
    except Exception:
        return ""

__all__ = [
    'pytesseract',
    'TextBlock',
    'OCREngine',
    'OCREngineFactory',
    'extract_text',
    '_ensure_min_size',
    '_is_garbage',
    '_is_block_noise',
    '_deskew',
    '_morphological_cleanup',
    'merge_text_blocks',
    'get_background_color',
    'is_ui_region',
    'filter_ui_blocks',
    'detect_speech_bubbles',
    'extract_bubble_regions',
    'extract_text_from_bubbles'
]
