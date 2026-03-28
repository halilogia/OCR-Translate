"""
OCR-TRANSLATE — Dual-Engine OCR Motoru (AAA Architecture)
Hem Tesseract hem EasyOCR desteği sunan esnek, nesne yönelimli mimari.
İlham: tomkam1702/OCR-Translator
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict

import cv2
import numpy as np
import pytesseract
import torch
import easyocr

import config
from config import OCR_LANG, OCR_PSM, OCR_ENGINE_TYPE

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
    0.15  # Manga/stylized fontlarda düşük güven normal, noise filter yakalar
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


class EasyOCREngine(OCREngine):
    """
    Derin Öğrenme tabanlı EasyOCR motoru.
    Gürültülü ve karmaşık sahnelerde (oyun içi, düşük ışık) üstündür.
    """

    def __init__(self) -> None:
        self._reader = None
        self._gpu = torch.cuda.is_available()
        self._langs = ["en"] if OCR_LANG == "eng" else [OCR_LANG]
        logger.info("EasyOCREngine başlatılıyor (GPU=%s)", self._gpu)

    def _get_reader(self):
        if self._reader is None:
            self._reader = easyocr.Reader(self._langs, gpu=self._gpu)
        return self._reader

    def extract_blocks(self, image: np.ndarray) -> List[TextBlock]:
        try:
            reader = self._get_reader()
            processed = self._preprocess(image)
            results = reader.readtext(processed)

            blocks = []
            for bbox, text, conf in results:
                text = text.strip()
                if not text or conf < _MIN_CONF_SCORE:
                    continue

                # Gürültü filtresi
                if _is_block_noise(text):
                    continue

                # EasyOCR bbox: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                # [x, y, w, h] formatına dönüştür
                x = int(min(p[0] for p in bbox))
                y = int(min(p[1] for p in bbox))
                w = int(max(p[0] for p in bbox) - x)
                h = int(max(p[1] for p in bbox) - y)

                blocks.append(TextBlock(text=text, box=[x, y, w, h], conf=conf))

            return blocks
        except Exception as e:
            logger.error("EasyOCR hatası: %s", e)
            return []

    def extract_text(self, image: np.ndarray) -> str:
        blocks = self.extract_blocks(image)
        return " ".join([b.text for b in blocks]).strip()

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        scaled = _ensure_min_size(image, target_width=1200)
        # Renkli denoising (EasyOCR renkli girişte daha iyi çalışır)
        try:
            denoised = cv2.fastNlMeansDenoisingColored(scaled, None, 8, 8, 7, 21)
        except Exception:
            denoised = cv2.bilateralFilter(scaled, 9, 75, 75)
        gray = cv2.cvtColor(denoised, cv2.COLOR_RGB2GRAY)
        # CLAHE + sharpening kombinasyonu
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        # Unsharp mask
        gaussian = cv2.GaussianBlur(enhanced, (0, 0), 2)
        return cv2.addWeighted(enhanced, 1.3, gaussian, -0.3, 0)


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

            # Tüm pipeline'ları dene, en çok anlamlı bloğu vereni seç
            best_blocks: List[TextBlock] = []
            best_score = -1

            for name, processed in pipelines.items():
                data = pytesseract.image_to_data(
                    processed, config=self._config, output_type=pytesseract.Output.DICT
                )

                # Satır bazlı gruplama: Aynı line_num'a ait kelimeleri soldan sağa birleştir
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

                # Her satırı tek bloğa dönüştür
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

                    if w_box < 30:
                        continue

                    min_conf = min(w["conf"] for w in words)
                    blocks.append(
                        TextBlock(
                            text=line_text, box=[x, y, w_box, h_box], conf=min_conf
                        )
                    )

                # Skor: toplam alfabetik karakter sayısı (en çok gerçek metin içeren)
                score = sum(sum(1 for c in b.text if c.isalpha()) for b in blocks)
                if score > best_score:
                    best_score = score
                    best_blocks = blocks

            return best_blocks
        except Exception as e:
            logger.error("Tesseract extract_blocks hatası: %s", e)
            return []

    def extract_text(self, image: np.ndarray) -> str:
        try:
            # 0. Dinamik PSM Listesi
            psm_modes = [config.OCR_PSM, 3] if config.OCR_PSM != 3 else [3, 6]

            best_text = ""
            best_quality = 0.0

            for psm in psm_modes:
                current_config = f"--oem 3 --psm {psm} -l {config.OCR_LANG}"

                # Tesseract için çoklu pipeline (En iyi sonucu seç)
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

                # Eğer ilk turda çok iyi sonuç gelirse ikinci PSM'yi deneme (Hız optimizasyonu)
                if best_quality > 0.85:
                    break

            if best_quality < 0.25:  # Kalite eşiği esnetildi
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

        # 0. Adaptive Denoising (NLMeans - gürültü tipine göre adapte olur)
        try:
            if scaled.dtype != np.uint8:
                scaled = scaled.astype(np.uint8)
            denoised = cv2.fastNlMeansDenoisingColored(scaled, None, 10, 10, 7, 21)
        except Exception:
            denoised = cv2.bilateralFilter(scaled, 9, 75, 75)

        # 1. Grayscale & Adaptive Contrast (CLAHE)
        gray = cv2.cvtColor(denoised, cv2.COLOR_RGB2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        high_contrast = clahe.apply(gray)

        # 2. Keskinleştirme (Unsharp Mask - daha doğal sharpening)
        gaussian = cv2.GaussianBlur(high_contrast, (0, 0), 3)
        sharpened = cv2.addWeighted(high_contrast, 1.5, gaussian, -0.5, 0)

        # 3. Deskew (eğik metin düzeltme)
        _, binary_for_deskew = cv2.threshold(
            sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        deskewed = _deskew(binary_for_deskew)
        # Deskew sonrası sharpened'i de aynı açıyla döndür
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

        # 4. Eşikleme (Thresholding) Pipeline'ları
        # Pipeline A: Otsu + Morphological Cleanup
        _, otsu = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        otsu = _morphological_cleanup(otsu)

        # Pipeline B: Adaptive + Morphological Cleanup
        adaptive = cv2.adaptiveThreshold(
            sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        adaptive = _morphological_cleanup(adaptive)

        # Pipeline C: Inverted (Siyah arka plan metinleri için)
        inverted = cv2.bitwise_not(otsu)

        # Pipeline D: Otsu + CLAHE (düşük kontrast için)
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
        # Uzunluk bonusu (çok kısa metinler genellikle gürültüdür)
        length_bonus = min(1.0, len(text) / 5.0)
        return ratio * length_bonus


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
            import base64
            import requests

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


class OCREngineFactory:
    """Motor seçimini yöneten fabrika sınıfı."""

    _instances = {}

    @classmethod
    def get_engine(cls, engine_type: Optional[str] = None) -> OCREngine:
        if engine_type is None:
            engine_type = config.OCR_ENGINE_TYPE

        if engine_type not in cls._instances:
            if engine_type == "tesseract":
                cls._instances[engine_type] = TesseractEngine()
            elif engine_type == "vision":
                cls._instances[engine_type] = VisionLLMEngine()
            else:
                cls._instances[engine_type] = EasyOCREngine()
        return cls._instances[engine_type]


def extract_text(image: np.ndarray) -> str:
    """Geriye dönük uyumluluk için ana giriş noktası."""
    # Çalışma anında config'e göre motoru seçer
    engine = OCREngineFactory.get_engine(config.OCR_ENGINE_TYPE)
    return engine.extract_text(image)


# region YARDIMCI FONKSİYONLAR
def merge_text_blocks(
    blocks: List[TextBlock], x_threshold: int = 40, y_threshold: int = 15
) -> List[TextBlock]:
    """
    Kelimeleri veya satırları mantıklı paragraflar haline getirir.
    MORT-Style 'Natural Overlay' için gereklidir.
    İki aşamalı: Satır içi birleştirme → Dikey paragraf birleştirme.
    """
    if not blocks:
        return []
    if len(blocks) == 1:
        return blocks

    # Minimum piksel boyutu filtresi (çok küçük bloklar gürültüdür)
    min_w, min_h = 20, 10
    blocks = [b for b in blocks if b.box[2] >= min_w and b.box[3] >= min_h]
    if not blocks:
        return []
    if len(blocks) == 1:
        return blocks

    # Y koordinatına göre sırala
    sorted_blocks = sorted(blocks, key=lambda b: (b.box[1], b.box[0]))

    # Aşama 1: Satırları oluştur (Y koordinatına göre grupla)
    rows: List[List[TextBlock]] = []
    for block in sorted_blocks:
        placed = False
        for row in rows:
            # Satırdaki herhangi bir blokla Y örtüşmesi var mı?
            row_y_min = min(b.box[1] for b in row)
            row_y_max = max(b.box[1] + b.box[3] for b in row)
            block_y = block.box[1]
            block_y_max = block_y + block.box[3]

            if (
                block_y < row_y_max + y_threshold
                and block_y_max > row_y_min - y_threshold
            ):
                row.append(block)
                placed = True
                break
        if not placed:
            rows.append([block])

    # Her satırı X koordinatına göre sırala ve satır içi blokları birleştir
    merged_rows: List[TextBlock] = []
    for row in rows:
        row.sort(key=lambda b: b.box[0])
        current = row[0]
        for i in range(1, len(row)):
            next_b = row[i]
            x_dist = next_b.box[0] - (current.box[0] + current.box[2])
            if x_dist < x_threshold:
                new_x = min(current.box[0], next_b.box[0])
                new_y = min(current.box[1], next_b.box[1])
                new_w = (
                    max(current.box[0] + current.box[2], next_b.box[0] + next_b.box[2])
                    - new_x
                )
                new_h = (
                    max(current.box[1] + current.box[3], next_b.box[1] + next_b.box[3])
                    - new_y
                )
                current = TextBlock(
                    text=current.text + " " + next_b.text,
                    box=[new_x, new_y, new_w, new_h],
                    conf=min(current.conf, next_b.conf),
                )
            else:
                merged_rows.append(current)
                current = next_b
        merged_rows.append(current)

    # Aşama 2: Dikey paragraf birleştirme (hizalı ve yakın satırlar)
    if len(merged_rows) <= 1:
        return merged_rows

    merged_rows.sort(key=lambda b: (b.box[1], b.box[0]))
    paragraphs: List[TextBlock] = [merged_rows[0]]

    for i in range(1, len(merged_rows)):
        prev = paragraphs[-1]
        curr = merged_rows[i]

        prev_bottom = prev.box[1] + prev.box[3]
        vertical_gap = curr.box[1] - prev_bottom

        # X hizalaması kontrolü (paragraf üyeliği)
        x_overlap = not (
            curr.box[0] + curr.box[2] < prev.box[0]
            or curr.box[0] > prev.box[0] + prev.box[2]
        )
        x_aligned = abs(curr.box[0] - prev.box[0]) < x_threshold * 2

        # Satır yüksekliği tahmini
        line_height = max(prev.box[3], curr.box[3])

        if vertical_gap < line_height * 2.0 and (x_overlap or x_aligned):
            new_x = min(prev.box[0], curr.box[0])
            new_y = min(prev.box[1], curr.box[1])
            new_w = max(prev.box[0] + prev.box[2], curr.box[0] + curr.box[2]) - new_x
            new_h = max(prev.box[1] + prev.box[3], curr.box[1] + curr.box[3]) - new_y
            paragraphs[-1] = TextBlock(
                text=prev.text + " " + curr.text,
                box=[new_x, new_y, new_w, new_h],
                conf=min(prev.conf, curr.conf),
            )
        else:
            paragraphs.append(curr)

    return paragraphs


def get_background_color(image: np.ndarray, box: List[int]) -> tuple:
    """
    Metin bloğunun etrafındaki baskın arka plan rengini belirler (Color Sampling).
    MORT-Style maskeleme için kullanılır.
    Köşe bazlı örnekleme + medyan filtre ile daha doğru sonuç verir.
    """
    try:
        x, y, w, h = box
        pad = max(8, min(w, h) // 4)  # Dinamik padding (blok boyutuna göre)
        img_h, img_w = image.shape[:2]

        # Genişletilmiş alan
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(img_w, x + w + pad)
        y2 = min(img_h, y + h + pad)

        # Köşe bölgelerini örnekle (metin bölgesi dışındaki arka plan)
        corner_size = min(pad, 20)
        corners = []

        # Sol üst köşe
        cx1, cy1 = max(0, x1), max(0, y1)
        cx2, cy2 = min(img_w, x1 + corner_size), min(img_h, y1 + corner_size)
        if cx2 > cx1 and cy2 > cy1:
            corners.append(image[cy1:cy2, cx1:cx2])

        # Sağ üst köşe
        cx1, cy1 = max(0, x2 - corner_size), max(0, y1)
        cx2, cy2 = min(img_w, x2), min(img_h, y1 + corner_size)
        if cx2 > cx1 and cy2 > cy1:
            corners.append(image[cy1:cy2, cx1:cx2])

        # Sol alt köşe
        cx1, cy1 = max(0, x1), max(0, y2 - corner_size)
        cx2, cy2 = min(img_w, x1 + corner_size), min(img_h, y2)
        if cx2 > cx1 and cy2 > cy1:
            corners.append(image[cy1:cy2, cx1:cx2])

        # Sağ alt köşe
        cx1, cy1 = max(0, x2 - corner_size), max(0, y2 - corner_size)
        cx2, cy2 = min(img_w, x2), min(img_h, y2)
        if cx2 > cx1 and cy2 > cy1:
            corners.append(image[cy1:cy2, cx1:cx2])

        if not corners:
            # Fallback: tüm padding bölgesi
            roi = image[y1:y2, x1:x2]
            if roi.size == 0:
                return (0, 0, 0)
            avg_color = cv2.mean(roi)[:3]
            return tuple(map(int, avg_color))

        # Tüm köşe piksellerini birleştir ve medyan al (outlier dayanıklılığı)
        all_pixels = np.concatenate([c.reshape(-1, 3) for c in corners])
        median_color = np.median(all_pixels, axis=0)
        return tuple(map(int, median_color))
    except Exception:
        return (0, 0, 0)


def _ensure_min_size(image: np.ndarray, target_width: int = 1500) -> np.ndarray:
    h, w = image.shape[:2]
    if w >= target_width:
        return image
    scale = target_width / w
    return cv2.resize(
        image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC
    )


def _deskew(image: np.ndarray) -> np.ndarray:
    """Görüntüdeki metin eğikliğini düzeltir (Deskew)."""
    coords = np.column_stack(np.where(image > 0))
    if len(coords) < 50:
        return image
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.5:
        return image
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def _morphological_cleanup(binary: np.ndarray) -> np.ndarray:
    """İkili görüntüdeki küçük noktaları ve boşlukları kapatır."""
    kernel_small = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_small, iterations=1)
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel_close, iterations=1)
    return closed


def _is_garbage(text: str) -> bool:
    cleaned = text.strip()
    if len(cleaned) < _MIN_TEXT_LENGTH:
        return True
    alpha_count = sum(1 for c in cleaned if c.isalpha() or c.isspace())
    if not cleaned:
        return True
    if alpha_count / len(cleaned) < (1 - _GARBAGE_RATIO_THRESHOLD):
        return True
    return False


def _is_block_noise(text: str) -> bool:
    """
    Blok seviyesinde gürültü tespiti. Tek karakterli semboller,
    rakam-karışık gürültü ve teknik kalıntıları filtreler.
    extract_blocks() içinde kullanılır.
    """
    cleaned = text.strip()
    if not cleaned:
        return True

    # 1-2 karakter: HER ZAMAN gürültü (tek kelime bile değil)
    if len(cleaned) <= 2:
        return True

    # 3 karakter ve küçük: en az %60 harf olmalı
    if len(cleaned) <= 4:
        alpha = sum(1 for c in cleaned if c.isalpha())
        return alpha / len(cleaned) < 0.6

    # Standart garbage kontrolü
    if _is_garbage(cleaned):
        return True

    # Teknik gürültü kontrolü
    if _is_technical_noise(cleaned):
        return True

    return False


def _is_technical_noise(text: str) -> bool:
    """Teknik gürültüleri (Dashboard metni, kod vb.) tespit eder."""
    # URL ve domain filtresi
    if re.search(
        r"https?://|www\.|\.com|\.org|\.net|\.io|toonily|chapter-", text, re.IGNORECASE
    ):
        return True

    # Dashboard ve sistem kelimeleri
    noise_keywords = [
        "OCR-TRANSLATE",
        "interval",
        "model",
        "vision",
        "inplace",
        "engine",
        "REFRESH",
        "DIAGNOSTIC",
        "SELECT AREA",
        "STATUS",
        "TRANSLATION",
        "Atmosfer:",
        "Gürültüyü",
        "Diyalog akışı",
        "Seçici çeviri",
        "Teknik filtre",
        "Format:",
        "Çeviri:",
        "Translation:",
    ]
    u_text = text.upper()
    count = sum(1 for k in noise_keywords if k.upper() in u_text)

    # Metnin çok küçük bir kısmı harfse veya teknik kelime yoğunluğu fazlaysa yoksay
    return count >= 2 or text.strip().startswith(("{", "["))


# endregion
