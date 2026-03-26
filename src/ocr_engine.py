"""
OCR-TRANSLATE — OCR Motoru
Tesseract ile ekran görüntüsünden metin çıkarma.
"""

import cv2
import numpy as np
import pytesseract

from config import OCR_LANG, OCR_PSM


def preprocess_image(image: np.ndarray) -> np.ndarray:
    """
    OCR doğruluğunu artırmak için görüntü ön işleme.
    Altyazılar genellikle açık renkli metin, koyu arka plan üzerinedir.
    """
    # Gri tonlamaya çevir
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

    # Kontrast artırma (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Otsu thresholding — metin ve arka planı otomatik ayırır
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return binary


def extract_text(image: np.ndarray) -> str:
    """
    Verilen görüntüden İngilizce metin çıkarır.
    Ön işleme uygulanmış görüntü Tesseract'a verilir.
    """
    processed = preprocess_image(image)

    custom_config = f"--oem 3 --psm {OCR_PSM} -l {OCR_LANG}"
    raw_text: str = pytesseract.image_to_string(processed, config=custom_config)

    # Temizlik: boş satırları ve gereksiz boşlukları kaldır
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    return " ".join(lines)
