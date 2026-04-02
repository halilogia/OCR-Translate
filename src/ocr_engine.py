"""
OCR-TRANSLATE — Multi-Engine OCR Motoru (AAA Architecture v2)
Manga-OCR, PaddleOCR, EasyOCR ve Tesseract desteği.
Konuşma balonu tespiti ve akıllı segmentasyon içerir.
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

import cv2
import numpy as np
import pytesseract

import config
from config import OCR_LANG, OCR_PSM, OCR_ENGINE_TYPE

logger = logging.getLogger(__name__)

# Lazy imports for optional dependencies
_manga_ocr_instance = None
_paddle_ocr_instance = None
_torch_loaded = False
_easyocr_loaded = False
_torch_loaded = False
_easyocr_loaded = False
_torch_loaded = False
_easyocr_loaded = False


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
                    import easyocr as _easyocr

                    _easyocr_loaded = True
                except ImportError:
                    raise RuntimeError("easyocr kurulu değil: pip install easyocr")
            self._reader = _easyocr.Reader(
                self._langs,
                gpu=self._gpu,
                model_storage_directory=None,
                download_enabled=True,
            )
        return self._reader

    def extract_blocks(self, image: np.ndarray) -> List[TextBlock]:
        try:
            reader = self._get_reader()
            processed = self._preprocess(image)

            # Manga için optimize edilmiş parametreler
            results = reader.readtext(
                processed,
                paragraph=False,  # Paragraf birleştirmeyi biz yapıyoruz
                min_size=10,  # Küçük metinleri de yakala
                text_threshold=0.6,  # Daha düşük eşik (stylized fontlar için)
                low_text=0.3,  # Düşük kontrastlı metinler
                link_threshold=0.3,  # Kelime bağlantı eşiği
                canvas_size=2560,  # Daha büyük canvas (detay kaybını önle)
                mag_ratio=1.5,  # Büyütme oranı
            )

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


class MangaOCREngine(OCREngine):
    """
    Manga-OCR: Japonca manga için özelleştirilmiş en iyi OCR.
    Kana, Kanji ve stylized fontlarda mükemmel sonuç verir.

    HYBRID MODE: EasyOCR ile koordinat tespiti + MangaOCR ile metin okuma
    Bu sayede hem doğru koordinatlar hem de doğru Japonca metin elde edilir.

    pip install manga-ocr
    """

    def __init__(self) -> None:
        global _manga_ocr_instance
        logger.info("MangaOCREngine başlatılıyor...")
        try:
            from manga_ocr import MangaOcr

            if _manga_ocr_instance is None:
                _manga_ocr_instance = MangaOcr()
            self._ocr = _manga_ocr_instance
            logger.info("MangaOCR başarıyla yüklendi")
        except ImportError:
            logger.error("manga-ocr yüklü değil! pip install manga-ocr")
            self._ocr = None

        # Koordinat tespiti için EasyOCR (Hybrid Mode)
        self._coord_detector = None

    def _get_coord_detector(self):
        """Lazy-load koordinat dedektörü (EasyOCR)"""
        if self._coord_detector is None:
            self._coord_detector = EasyOCREngine()
        return self._coord_detector

    def extract_blocks(self, image: np.ndarray) -> List[TextBlock]:
        """
        HYBRID MODE:
        1. EasyOCR ile metin bölgelerinin koordinatlarını tespit et
        2. Her bölgeyi MangaOCR ile oku (daha doğru Japonca)
        """
        if self._ocr is None:
            logger.warning("MangaOCR yok, sadece EasyOCR kullanılıyor")
            return self._get_coord_detector().extract_blocks(image)

        # 1. EasyOCR ile koordinatları al
        coord_blocks = self._get_coord_detector().extract_blocks(image)

        if not coord_blocks:
            # Fallback: Tüm görüntüyü tek blok olarak işle
            text = self.extract_text(image)
            if text:
                h, w = image.shape[:2]
                return [TextBlock(text=text, box=[0, 0, w, h], conf=0.95)]
            return []

        # 2. Her blok için MangaOCR ile metni oku
        result_blocks = []
        for block in coord_blocks:
            x, y, w, h = block.box
            # Blok bölgesini kırp (padding ekle)
            pad = 5
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(image.shape[1], x + w + pad)
            y2 = min(image.shape[0], y + h + pad)

            cropped = image[y1:y2, x1:x2]

            if cropped.size == 0:
                continue

            # MangaOCR ile oku
            manga_text = self._extract_text_from_crop(cropped)

            if manga_text:
                result_blocks.append(
                    TextBlock(
                        text=manga_text,
                        box=[x, y, w, h],  # Orijinal koordinatlar
                        conf=0.95,
                    )
                )
                logger.info(
                    f"[OCR-Manga-Hybrid] Block ({x},{y},{w},{h}): '{manga_text[:50]}'"
                )
            else:
                # MangaOCR başarısız olursa EasyOCR sonucunu kullan
                if block.text:
                    result_blocks.append(block)

        return result_blocks

    def _extract_text_from_crop(self, cropped: np.ndarray) -> str:
        """Kırpılmış görüntüden MangaOCR ile metin çıkar."""
        try:
            from PIL import Image

            if len(cropped.shape) == 2:
                pil_img = Image.fromarray(cropped)
            else:
                pil_img = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))

            text = self._ocr(pil_img)
            if text and not _is_garbage(text):
                return text.strip()
            return ""
        except Exception as e:
            logger.error("MangaOCR crop hatası: %s", e)
            return ""

    def extract_text(self, image: np.ndarray) -> str:
        """Tüm görüntüden tek metin çıkar (legacy)."""
        if self._ocr is None:
            logger.warning("MangaOCR kullanılamıyor, EasyOCR'a düşülüyor")
            return self._get_coord_detector().extract_text(image)

        try:
            from PIL import Image

            if len(image.shape) == 2:
                pil_img = Image.fromarray(image)
            else:
                pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

            text = self._ocr(pil_img)
            if text and not _is_garbage(text):
                logger.info("[OCR-Manga] Başarılı: '%s'", text[:100])
                return text.strip()
            return ""
        except Exception as e:
            logger.error("MangaOCR hatası: %s", e)
            return ""


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
            elif engine_type == "manga":
                cls._instances[engine_type] = MangaOCREngine()
            elif engine_type == "paddle":
                cls._instances[engine_type] = PaddleOCREngine()
            else:
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


# region KONUŞMA BALONU TESPİTİ (Speech Bubble Detection)


def detect_speech_bubbles(
    image: np.ndarray, min_area: int = 1000
) -> List[Tuple[int, int, int, int]]:
    """
    Manga/manhwa görüntüsünde konuşma balonlarını tespit eder.
    Beyaz veya açık renkli kapalı alanları bulur.

    Args:
        image: RGB numpy array
        min_area: Minimum balon alanı (piksel²)

    Returns:
        List of bounding boxes: [(x, y, w, h), ...]
    """
    try:
        # 1. Grayscale'e çevir
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image.copy()

        # 2. Beyaz/açık alanları bul (konuşma balonları genellikle beyaz)
        # Adaptive threshold ile değişken aydınlatmaya dayanıklılık
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            15,
            -5,  # Negatif C değeri beyaz alanları vurgular
        )

        # 3. Morfolojik işlemler: küçük gürültüyü temizle, balonları kapat
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_close)
        opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel_open)

        # 4. Kontur bulma
        contours, _ = cv2.findContours(
            opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        bubbles = []
        img_h, img_w = image.shape[:2]
        img_area = img_h * img_w

        for contour in contours:
            area = cv2.contourArea(contour)

            # Alan filtresi: çok küçük veya çok büyük alanları atla
            if area < min_area or area > img_area * 0.5:
                continue

            # Bounding box
            x, y, w, h = cv2.boundingRect(contour)

            # Aspect ratio filtresi: çok uzun/dar şekilleri atla
            aspect = w / h if h > 0 else 0
            if aspect < 0.2 or aspect > 5:
                continue

            # Compactness: Alan / (Çevre²) - daireler ve ovaller için yüksek
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                compactness = 4 * np.pi * area / (perimeter**2)
                if compactness < 0.15:  # Çok düzensiz şekilleri atla
                    continue

            # İç bölgenin ortalama parlaklığını kontrol et (beyaz olmalı)
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.drawContours(mask, [contour], -1, 255, -1)
            mean_brightness = cv2.mean(gray, mask=mask)[0]

            if mean_brightness < 180:  # Yeterince açık renkli değil
                continue

            bubbles.append((x, y, w, h))

        # Büyükten küçüğe sırala (öncelikli balonlar)
        bubbles.sort(key=lambda b: b[2] * b[3], reverse=True)

        logger.info("Tespit edilen konuşma balonu sayısı: %d", len(bubbles))
        return bubbles

    except Exception as e:
        logger.error("Konuşma balonu tespiti hatası: %s", e)
        return []


def extract_bubble_regions(
    image: np.ndarray, bubbles: List[Tuple[int, int, int, int]], padding: int = 5
) -> List[np.ndarray]:
    """
    Tespit edilen balonlardan görüntü bölgelerini çıkarır.

    Args:
        image: Orijinal görüntü
        bubbles: Bounding box listesi
        padding: Ek kenar boşluğu

    Returns:
        List of cropped images
    """
    regions = []
    img_h, img_w = image.shape[:2]

    for x, y, w, h in bubbles:
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(img_w, x + w + padding)
        y2 = min(img_h, y + h + padding)

        region = image[y1:y2, x1:x2]
        if region.size > 0:
            regions.append(region)

    return regions


def extract_text_from_bubbles(
    image: np.ndarray, engine: Optional[OCREngine] = None
) -> List[TextBlock]:
    """
    Konuşma balonlarını tespit edip sadece onlardan OCR yapar.
    UI elementlerini ve diğer gürültüyü otomatik olarak filtreler.

    Args:
        image: RGB görüntü
        engine: Kullanılacak OCR motoru (None ise varsayılan)

    Returns:
        TextBlock listesi
    """
    if engine is None:
        engine = OCREngineFactory.get_engine()

    # 1. Balonları tespit et
    bubbles = detect_speech_bubbles(image)

    if not bubbles:
        # Balon bulunamazsa tüm görüntüyü işle (fallback)
        logger.info("Konuşma balonu bulunamadı, tüm görüntü işleniyor")
        return engine.extract_blocks(image)

    # 2. Her balondan OCR yap
    all_blocks = []
    for i, (bx, by, bw, bh) in enumerate(bubbles):
        # Balon bölgesini kırp
        region = image[by : by + bh, bx : bx + bw]
        if region.size == 0:
            continue

        # OCR uygula
        blocks = engine.extract_blocks(region)

        # Koordinatları orijinal görüntüye göre ayarla
        for block in blocks:
            block.box[0] += bx
            block.box[1] += by
            all_blocks.append(block)

    logger.info("Balonlardan çıkarılan toplam blok: %d", len(all_blocks))
    return all_blocks


def is_ui_region(image: np.ndarray, box: List[int]) -> bool:
    """
    Verilen bölgenin UI elementi olup olmadığını kontrol eder.
    Toolbar, adres çubuğu, sekme gibi alanları tespit eder.
    Config'deki değerleri kullanır.
    """
    if not getattr(config, "ENABLE_UI_FILTER", True):
        return False

    x, y, w, h = box
    img_h, img_w = image.shape[:2]

    top_margin = getattr(config, "UI_TOP_MARGIN", 0.12)
    bottom_margin = getattr(config, "UI_BOTTOM_MARGIN", 0.05)
    side_margin = getattr(config, "UI_SIDE_MARGIN", 0.08)

    # Üst alan (toolbar/adres çubuğu/sekme çubuğu)
    if y < img_h * top_margin and h < img_h * 0.08:
        return True

    # Alt alan (durum çubuğu)
    if y > img_h * (1 - bottom_margin):
        return True

    # Sol/sağ kenarlar (sidebar)
    if (
        x < img_w * side_margin or x + w > img_w * (1 - side_margin)
    ) and w < img_w * 0.12:
        return True

    # Çok küçük alanlar (ikonlar, düğmeler)
    if w * h < 400:
        return True

    # Çok dar veya çok geniş oranlar (menü ögeleri, butonlar)
    aspect = w / h if h > 0 else 0
    if aspect > 8 or aspect < 0.1:
        return True

    return False


def filter_ui_blocks(blocks: List[TextBlock], image: np.ndarray) -> List[TextBlock]:
    """UI elementlerinden gelen blokları filtreler."""
    filtered = []
    for block in blocks:
        if not is_ui_region(image, block.box):
            filtered.append(block)
        else:
            logger.debug(
                "UI bloğu filtrelendi: %s", block.text[:30] if block.text else ""
            )
    return filtered


# endregion
