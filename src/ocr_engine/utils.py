"""
OCR-TRANSLATE — OCR Yardımcı Fonksiyonları
Metin bloklarını birleştirme, arka plan rengi tespiti ve ön işleme yardımcıları.
"""

import logging
import re
from typing import List

import cv2
import numpy as np

import config
from .base import TextBlock, _MIN_TEXT_LENGTH, _GARBAGE_RATIO_THRESHOLD

logger = logging.getLogger(__name__)


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
    alpha_count = sum(1 for c in cleaned if c.isalpha())
    effective_len = sum(1 for c in cleaned if not c.isspace())
    if not cleaned:
        return True
    if effective_len == 0:
        return True
    if alpha_count / effective_len < 0.55:
        return True

    # OCR gürültüsü: çok fazla büyük harf ve kısa token karışımı
    words = [w for w in re.findall(r"[A-Za-z]+", cleaned) if w]
    if words:
        upper_ratio = sum(1 for c in cleaned if c.isupper()) / max(
            1, sum(1 for c in cleaned if c.isalpha())
        )
        short_words = sum(1 for w in words if len(w) <= 2)
        if upper_ratio > 0.35 and short_words >= 2:
            return True

    if re.search(r"([A-Z0-9])\1{3,}", cleaned):
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
