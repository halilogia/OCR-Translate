"""
OCR-TRANSLATE — Vision LLM Engine
Ollama Vision modellerini kullanarak OCR yapar.
"""

import base64
import logging
from typing import List

import cv2
import numpy as np
import requests

import config

from .base import OCREngine, TextBlock
from .utils import _is_garbage, _is_technical_noise

logger = logging.getLogger(__name__)


class VisionLLMEngine(OCREngine):
    """
    Ollama Vision modellerini (glm-ocr, llama3.2-vision vb.) kullanarak OCR yapar.
    En yüksek doğruluk oranına sahiptir (Bağlam duyarlı).
    """

    def __init__(self) -> None:
        logger.info("VisionLLMEngine başlatılıyor (Dinamik Model Modu)")

    def extract_blocks(self, image: np.ndarray) -> List[TextBlock]:
        # Vision modelleri koordinat döndürmez, tüm alanı tek blok sayıyoruz
        text = self.extract_text(image)
        if not text:
            return []
        h, w = image.shape[:2]
        return [TextBlock(text=text, box=[0, 0, w, h], conf=0.99)]

    def extract_text(self, image: np.ndarray) -> str:
        model = getattr(config, "VISION_MODEL", "glm-ocr")
        try:
            # Görseli base64'e çevir
            _, buffer = cv2.imencode(".jpg", image)
            img_base64 = base64.b64encode(buffer).decode("utf-8")

            # Ollama Vision API çağrısı (AAA Prompting)
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model,
                    "prompt": (
                        "Task: Extract only the dialogue, narration, or story text from this image.\n"
                        "Rules:\n"
                        "- IGNORE all UI elements, buttons, menus, and system text.\n"
                        "- IGNORE technical words like 'model', 'interval', 'JSON', 'config'.\n"
                        "- If the image contains a person or character without text, return an empty string.\n"
                        "- Return ONLY the extracted text, no JSON, no explanations."
                    ),
                    "images": [img_base64],
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=30,
            )

            if response.status_code == 200:
                text = response.json().get("response", "").strip()
                if text and not _is_garbage(text) and not _is_technical_noise(text):
                    logger.info(
                        "[OCR-Vision] Başarılı okuma (%s): '%s'", model, text[:120]
                    )
                    return text
            return ""
        except Exception as e:
            logger.error("Vision OCR hatası (%s): %s", model, e)
            return ""
