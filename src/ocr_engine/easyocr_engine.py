"""
OCR-TRANSLATE — EasyOCR Engine
Derin Öğrenme tabanlı EasyOCR motoru.
Manga, manhwa ve gürültülü sahnelerde optimize edilmiştir.
"""

import logging
from typing import List, Tuple

import cv2
import numpy as np

from config import OCR_LANG
from .base import OCREngine, TextBlock, _MIN_CONF_SCORE
from .utils import _is_block_noise, _ensure_min_size

logger = logging.getLogger(__name__)

_easyocr_loaded = False
_torch_loaded = False


class EasyOCREngine(OCREngine):
    """
    Derin Öğrenme tabanlı EasyOCR motoru.
    Manga, manhwa ve gürültülü sahnelerde (oyun içi, düşük ışık) optimize edilmiştir.
    """

    def __init__(self) -> None:
        self._reader = None
        global _torch_loaded
        if not _torch_loaded:
            try:
                import torch as _torch

                _torch_loaded = True
                self._gpu = _torch.cuda.is_available()
            except ImportError:
                self._gpu = False
        else:
            self._gpu = False
        # Manga/manhwa için çoklu dil desteği
        self._langs = self._get_optimal_langs()
        logger.info(
            "EasyOCREngine başlatılıyor (GPU=%s, langs=%s)", self._gpu, self._langs
        )

    def _get_optimal_langs(self) -> List[str]:
        """Manga/manhwa için optimal dil listesi."""
        base_lang = "en" if OCR_LANG == "eng" else OCR_LANG
        # Korece manhwa için
        if base_lang in ["ko", "korean"]:
            return ["ko", "en"]
        # Japonca manga için
        elif base_lang in ["ja", "japanese"]:
            return ["ja", "en"]
        # Çince manhua için
        elif base_lang in ["ch", "ch_sim", "chinese"]:
            return ["ch_sim", "en"]
        return [base_lang]

    def _get_reader(self):
        if self._reader is None:
            global _easyocr_loaded
            if not _easyocr_loaded:
                try:
                    import easyocr

                    self._easyocr_module = easyocr
                    _easyocr_loaded = True
                except ImportError:
                    raise RuntimeError("easyocr kurulu değil: pip install easyocr")

            # Use the module reference stored in the instance if available, or the global one
            reader_module = getattr(self, "_easyocr_module", None)
            if reader_module is None:
                import easyocr

                reader_module = easyocr

            self._reader = reader_module.Reader(
                self._langs,
                gpu=self._gpu,
                model_storage_directory=None,
                download_enabled=True,
            )
        return self._reader

    def extract_blocks(self, image: np.ndarray) -> List[TextBlock]:
        try:
            reader = self._get_reader()
            processed, scale = self._preprocess_with_scale(image)

            # Manga için optimize edilmiş parametreler
            results = reader.readtext(
                processed,
                paragraph=False,
                min_size=10,
                text_threshold=0.6,
                low_text=0.3,
                link_threshold=0.3,
                canvas_size=2560,
                mag_ratio=1.5,
            )

            blocks = []
            for bbox, text, conf in results:
                text = text.strip()
                if not text or conf < _MIN_CONF_SCORE:
                    continue

                if _is_block_noise(text):
                    continue

                # EasyOCR bbox: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] -> [x, y, w, h]
                x = int(min(p[0] for p in bbox))
                y = int(min(p[1] for p in bbox))
                w = int(max(p[0] for p in bbox) - x)
                h = int(max(p[1] for p in bbox) - y)

                # ÖNEMLİ: Koordinatları orijinal görüntü boyutuna geri ölçekle
                if scale != 1.0:
                    x, y, w, h = (
                        int(x / scale),
                        int(y / scale),
                        int(w / scale),
                        int(h / scale),
                    )

                blocks.append(TextBlock(text=text, box=[x, y, w, h], conf=conf))

            return blocks
        except Exception as e:
            logger.error("EasyOCR hatası: %s", e)
            return []

    def _preprocess_with_scale(self, image: np.ndarray) -> Tuple[np.ndarray, float]:
        """Görüntüyü işler ve kullanılan ölçek faktörünü döner."""
        h, w = image.shape[:2]
        target_width = 1500
        scale = 1.0
        if w < target_width:
            scale = target_width / w
            image = cv2.resize(
                image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC
            )

        # Diğer ön işlemler... (renk uzayı vb.)
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

        return image, scale

    def extract_text(self, image: np.ndarray) -> str:
        blocks = self.extract_blocks(image)
        return " ".join([b.text for b in blocks]).strip()

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """Manga/manhwa için optimize edilmiş ön işleme."""
        # 1. Minimum boyut garantisi
        scaled = _ensure_min_size(image, target_width=1400)

        # 2. Renk uzayı kontrolü
        if len(scaled.shape) == 2:
            # Grayscale ise RGB'ye çevir (EasyOCR RGB bekler)
            scaled = cv2.cvtColor(scaled, cv2.COLOR_GRAY2RGB)

        # 3. Adaptif denoising (manga için hafif)
        try:
            # Manga genellikle temiz çizgi olduğu için hafif denoising
            denoised = cv2.fastNlMeansDenoisingColored(scaled, None, 5, 5, 7, 15)
        except Exception:
            denoised = scaled

        # 4. Kontrast iyileştirme (LAB renk uzayında)
        try:
            lab = cv2.cvtColor(denoised, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            enhanced = cv2.merge([l, a, b])
            result = cv2.cvtColor(enhanced, cv2.COLOR_LAB2RGB)
        except Exception:
            result = denoised

        # 5. Hafif keskinleştirme (metin kenarları için)
        kernel = (
            np.array([[-0.5, -0.5, -0.5], [-0.5, 5.0, -0.5], [-0.5, -0.5, -0.5]]) / 1.5
        )
        try:
            result = cv2.filter2D(result, -1, kernel)
        except Exception:
            pass

        return result
