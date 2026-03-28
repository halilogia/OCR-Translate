import logging
import re
import requests
import base64
import cv2
import numpy as np
import config

logger = logging.getLogger(__name__)


class CognitiveRefiner:
    """
    OCR çıktılarını (metin) ve orijinal görüntüyü (resim) birlikte analiz eden
    akıllı (Multi-modal) düzeltme katmanı. (Sovereign Quality).
    """

    def __init__(self):
        # Kural Tabanlı Hızlı Düzeltmeler (genişletilmiş)
        self.rules = [
            # Sayı-harf karışıklıkları
            (r"\b8ACK\b", "BACK"),
            (r"\bT DON'T\b", "I DON'T"),
            (r"\bT8\b", "IS"),
            (r"\b0F\b", "OF"),
            (r"\bl\b(?=\s)", "I"),
            (r"\byOUu\b", "YOU"),
            (r"!\/ T", "! I"),
            # Yaygın OCR hataları
            (r"\bTm\b", "I'm"),
            (r"\bTl\b", "I'll"),
            (r"\bTve\b", "I've"),
            (r"\bth1s\b", "this"),
            (r"\bwh1ch\b", "which"),
            (r"\bw1th\b", "with"),
            (r"\bfr0m\b", "from"),
            (r"\bwh0\b", "who"),
            (r"\bwh4t\b", "what"),
            (r"\bth4t\b", "that"),
            (r"\bwh3n\b", "when"),
            (r"\b5he\b", "She"),
            (r"\bh3\b", "he"),
            (r"\bth3\b", "the"),
            # Tek karakter düzeltmeleri
            (r"(?<![a-zA-Z])1(?![0-9])", "l"),  # yalniz 1 -> l (dikkatli)
            # Fazla bosluk temizligi
            (r"\s{2,}", " "),
        ]

    def refine(self, text: str, image: np.ndarray = None) -> str:
        """Metni hem kural hem de Görsel/LLM desteği ile temizler."""
        if not text.strip():
            return text

        # Adım 1: Kural Tabanlı Hızlı Düzeltme
        refined = text
        for pattern, replacement in self.rules:
            refined = re.sub(pattern, replacement, refined, flags=re.IGNORECASE)

        # Adım 2: Satır içi temizlik
        refined = refined.strip()

        # Adım 3: Multi-modal Görsel Destekli Düzeltme (Eğer aktifse)
        if config.ENABLE_REFINER and image is not None:
            refined = self._visual_refine(refined, image)

        return refined

    def _visual_refine(self, text: str, image: np.ndarray) -> str:
        """Görüntü ve metni birlikte kullanarak OCR hatalarını düzeltir."""
        if image is None:
            return text

        try:
            # Görseli base64'e çevir (JPEG kalite 85 - hız/kalite dengesi)
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, 85]
            _, buffer = cv2.imencode(".jpg", image, encode_params)
            img_base64 = base64.b64encode(buffer).decode("utf-8")

            # Multi-modal Prompt (kısa ve odaklı)
            prompt = (
                f"OCR Output: '{text}'\n\n"
                "Task: Fix OCR mistakes in the text using the image context. Keep the original language.\n"
                "Rules:\n"
                "- Fix errors like 'T' vs 'I', '8' vs 'B', '0' vs 'O', '1' vs 'l'.\n"
                "- DO NOT translate.\n"
                "- DO NOT explain.\n"
                "- Return ONLY the corrected text."
            )

            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": config.REFINER_MODEL,
                    "prompt": prompt,
                    "images": [img_base64],
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 256},
                },
                timeout=10,
            )

            if response.status_code == 200:
                corrected = response.json().get("response", "").strip()
                if corrected and not self._is_prompt_leak(corrected):
                    logger.info(
                        "[COGNITIVE-REFINER] Girdi: %s -> Düzeltildi: %s",
                        text[:30],
                        corrected[:30],
                    )
                    return corrected
                elif corrected:
                    logger.warning(
                        "[COGNITIVE-REFINER] Prompt sızıntısı tespit edildi, orijinal metin kullanılıyor."
                    )
            return text
        except requests.exceptions.Timeout:
            logger.warning(
                "[COGNITIVE-REFINER] Timeout (10s), kural tabanlı düzeltme yeterli."
            )
            return text
        except Exception as e:
            logger.error("[COGNITIVE-REFINER] Hata: %s", e)
            return text

    def _is_prompt_leak(self, text: str) -> bool:
        """Modelin kendi sistem promptunu döndürüp döndürmediğini kontrol eder."""
        leak_patterns = [
            "Atmosfer:",
            "Gürültüyü",
            "Diyalog akışı",
            "Seçici çeviri",
            "Teknik filtre",
            "Format:",
            "Kelime kelime",
            "duygusal ve dinamik",
            "Kullanıcıyı içine",
            "manga/oyunlara uygun",
            "görüyorsanız",
            "boş bir string",
            "çevrilmiş metni",
            "Sadece çevrilmiş",
            "Task:",
            "Guidelines:",
            "OCR Output:",
            "Return ONLY",
            "DO NOT translate",
            "DO NOT add",
            "DO NOT explain",
            "Keep the original",
            "Fix OCR mistakes",
            "Rules:",
        ]
        u = text.upper()
        return any(p.upper() in u for p in leak_patterns)
