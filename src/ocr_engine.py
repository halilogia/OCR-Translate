"""
OCR-TRANSLATE — OCR Engine (Legacy Wrapper)
Bu dosya geriye dönük uyumluluk için korunmaktadır.
Tüm fonksiyonellik src/ocr_engine/ paketine taşınmıştır.
"""

from ocr_engine import (
    TextBlock,
    OCREngine,
    OCREngineFactory,
    extract_text,
    merge_text_blocks,
    get_background_color,
    is_ui_region,
    filter_ui_blocks,
    detect_speech_bubbles,
    extract_bubble_regions,
    extract_text_from_bubbles,
)

__all__ = [
    "TextBlock",
    "OCREngine",
    "OCREngineFactory",
    "extract_text",
    "merge_text_blocks",
    "get_background_color",
    "is_ui_region",
    "filter_ui_blocks",
    "detect_speech_bubbles",
    "extract_bubble_regions",
    "extract_text_from_bubbles",
]
