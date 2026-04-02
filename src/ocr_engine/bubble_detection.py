"""
OCR-TRANSLATE — Speech Bubble Detection
Konuşma balonu tespiti ve bölge çıkarma fonksiyonları.
"""

import logging
from typing import List, Tuple, Optional

import cv2
import numpy as np

from .base import TextBlock, OCREngine

logger = logging.getLogger(__name__)


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

            # Balonun merkeze yakınlığını kontrol et (Kırpılmış görüntülerde UI gürültüsü kenardadır)
            cx, cy = x + w / 2, y + h / 2
            if cx < 20 or cx > img_w - 20 or cy < 20 or cy > img_h - 20:
                if w < 50 or h < 50:
                    continue  # Kenardaki çok küçük şeyler gürültüdür

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


# endregion


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
    from .factory import OCREngineFactory

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
            # DİKKAT: block.box bir list [x, y, w, h] olmalıdır.
            block.box[0] = int(block.box[0]) + bx
            block.box[1] = int(block.box[1]) + by
            all_blocks.append(block)

    logger.info("Balonlardan çıkarılan toplam blok: %d", len(all_blocks))
    return all_blocks
