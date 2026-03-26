"""
OCR-TRANSLATE — Test Yapılandırması
Ortak fixture'lar ve yardımcılar.
"""

import numpy as np
import pytest


@pytest.fixture
def sample_rgb_image() -> np.ndarray:
    """Beyaz metin, siyah arka plan (RGB) — altyazı simülasyonu."""
    img = np.zeros((100, 400, 3), dtype=np.uint8)
    # Beyaz dikdörtgen bant (metin simülasyonu)
    img[30:70, 50:350] = 255
    return img


@pytest.fixture
def sample_bgr_image() -> np.ndarray:
    """BGR formatında test görüntüsü."""
    img = np.zeros((100, 400, 3), dtype=np.uint8)
    # Mavi kanal yüksek (BGR'de ilk kanal)
    img[30:70, 50:350, 0] = 255  # B
    img[30:70, 50:350, 1] = 0  # G
    img[30:70, 50:350, 2] = 0  # R
    return img


@pytest.fixture
def sample_bgra_image() -> np.ndarray:
    """BGRA formatında test görüntüsü (mss çıktısı simülasyonu)."""
    img = np.zeros((100, 400, 4), dtype=np.uint8)
    img[30:70, 50:350, 0] = 255  # B
    img[30:70, 50:350, 1] = 128  # G
    img[30:70, 50:350, 2] = 64  # R
    img[30:70, 50:350, 3] = 255  # A
    return img


@pytest.fixture
def sample_region() -> dict:
    """Geçerli bir Region dict'i."""
    return {"top": 100, "left": 200, "width": 800, "height": 100}
