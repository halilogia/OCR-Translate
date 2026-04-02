"""
OCR-TRANSLATE — Tesseract OCR Engine
"""

import logging
from typing import List

import cv2
import numpy as np
import pytesseract

import config
from config import OCR_LANG, OCR_PSM

from .base import OCREngine, TextBlock
from .utils import (
    _ensure_min_size,
    _deskew,
    _morphological_cleanup,
    _is_garbage,
    _is_block_noise,
)

logger = logging.getLogger(__name__)

_MIN_CONF_SCORE = 0.40


class TesseractEngine(OCREngine):
    """
    Klasik Tesseract motoru.
    Temiz metinlerde (Manga, doküman) çok hızlıdır ve satır bazlı tutarlıdır.
    """

    def __init__(self) -> None:
        logger.info("TesseractEngine başlatılıyor (PSM=%d)", OCR_PSM)
        self._config = f"--oem 3 --psm {OCR_PSM} -l {OCR_LANG}"

    def extract_blocks(self, image: np.ndarray) -> List[TextBlock]:
        try:
            pipelines = self._get_pipelines(image)

            best_blocks: List[TextBlock] = []
            best_score = -1

            h, w = image.shape[:2]
            target_width = 1200
            scale = target_width / w if w < target_width else 1.0

            for name, processed in pipelines.items():
                data = pytesseract.image_to_data(
                    processed, config=self._config, output_type=pytesseract.Output.DICT
                )

                lines: dict[tuple, list] = {}
                n_boxes = len(data["text"])
                for i in range(n_boxes):
                    text = data["text"][i].strip()
                    conf = float(data["conf"][i]) / 100.0
                    if not text or conf < _MIN_CONF_SCORE:
                        continue

                    key = (data["block_num"][i], data["line_num"][i])
                    if key not in lines:
                        lines[key] = []
                    lines[key].append(
                        {
                            "text": text,
                            "conf": conf,
                            "left": data["left"][i],
                            "top": data["top"][i],
                            "width": data["width"][i],
                            "height": data["height"][i],
                        }
                    )

                blocks = []
                for key, words in lines.items():
                    words.sort(key=lambda w: w["left"])
                    line_text = " ".join(w["text"] for w in words)
                    if _is_block_noise(line_text):
                        continue

                    x = min(w["left"] for w in words)
                    y = min(w["top"] for w in words)
                    x_max = max(w["left"] + w["width"] for w in words)
                    y_max = max(w["top"] + w["height"] for w in words)

                    w_box = x_max - x
                    h_box = y_max - y

                    if scale != 1.0:
                        x, y, w_box, h_box = (
                            int(x / scale),
                            int(y / scale),
                            int(w_box / scale),
                            int(h_box / scale),
                        )

                    if w_box < 10:
                        continue

                    blocks.append(
                        TextBlock(
                            text=line_text,
                            box=[x, y, w_box, h_box],
                            conf=min(w["conf"] for w in words),
                        )
                    )

                score = sum(len(b.text) for b in blocks)
                if score > best_score:
                    best_score = score
                    best_blocks = blocks

            return best_blocks
        except Exception as e:
            logger.error("Tesseract extract_blocks hatası: %s", e)
            return []

    def extract_text(self, image: np.ndarray) -> str:
        try:
            psm_modes = [config.OCR_PSM, 3] if config.OCR_PSM != 3 else [3, 6]

            best_text = ""
            best_quality = 0.0

            for psm in psm_modes:
                current_config = f"--oem 3 --psm {psm} -l {config.OCR_LANG}"

                pipelines = self._get_pipelines(image)

                for name, processed in pipelines.items():
                    text = pytesseract.image_to_string(
                        processed, config=current_config
                    ).strip()
                    if not text:
                        continue

                    quality = self._calculate_quality(text)
                    if quality > best_quality:
                        best_quality = quality
                        best_text = text
                        logger.debug(
                            "[OCR-Tess] Yeni en iyi (PSM=%d, %s, q=%.2f): %s",
                            psm,
                            name,
                            quality,
                            text[:50],
                        )

                if best_quality > 0.85:
                    break

            if best_quality < 0.25:
                return ""

            if _is_garbage(best_text):
                return ""

            logger.info(
                "[OCR-Tess] Başarılı okuma (q=%.2f): '%s'",
                best_quality,
                best_text[:120],
            )
            return best_text
        except Exception as e:
            logger.error("Tesseract hatası: %s", e)
            return ""

    def _get_pipelines(self, image: np.ndarray) -> dict:
        scaled = _ensure_min_size(image)

        try:
            if scaled.dtype != np.uint8:
                scaled = scaled.astype(np.uint8)
            denoised = cv2.fastNlMeansDenoisingColored(scaled, None, 10, 10, 7, 21)
        except Exception:
            denoised = cv2.bilateralFilter(scaled, 9, 75, 75)

        gray = cv2.cvtColor(denoised, cv2.COLOR_RGB2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        high_contrast = clahe.apply(gray)

        gaussian = cv2.GaussianBlur(high_contrast, (0, 0), 3)
        sharpened = cv2.addWeighted(high_contrast, 1.5, gaussian, -0.5, 0)

        _, binary_for_deskew = cv2.threshold(
            sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        deskewed = _deskew(binary_for_deskew)
        if deskewed is not binary_for_deskew:
            coords = np.column_stack(np.where(binary_for_deskew > 0))
            if len(coords) >= 50:
                angle = cv2.minAreaRect(coords)[-1]
                if angle < -45:
                    angle = -(90 + angle)
                else:
                    angle = -angle
                if abs(angle) >= 0.5:
                    h, w = sharpened.shape[:2]
                    center = (w // 2, h // 2)
                    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
                    sharpened = cv2.warpAffine(
                        sharpened,
                        matrix,
                        (w, h),
                        flags=cv2.INTER_CUBIC,
                        borderMode=cv2.BORDER_REPLICATE,
                    )

        _, otsu = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        otsu = _morphological_cleanup(otsu)

        adaptive = cv2.adaptiveThreshold(
            sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        adaptive = _morphological_cleanup(adaptive)

        inverted = cv2.bitwise_not(otsu)

        otsu_clahe = cv2.threshold(
            high_contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )[1]

        return {
            "otsu": otsu,
            "adaptive": adaptive,
            "inverted": inverted,
            "otsu_clahe": otsu_clahe,
        }

    def _calculate_quality(self, text: str) -> float:
        """Metnin kalitesini (alfabetik oran, uzunluk vb.) basitçe puanlar."""
        if not text:
            return 0.0
        alpha_count = sum(1 for c in text if c.isalpha() or c.isspace())
        ratio = alpha_count / len(text)
        length_bonus = min(1.0, len(text) / 5.0)
        return ratio * length_bonus
