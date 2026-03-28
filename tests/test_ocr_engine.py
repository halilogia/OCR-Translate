"""
OCR-TRANSLATE — OCR Engine Birim & Kenar Durum Testleri
=======================================================
Test Framework: pytest
Dogruladigi Modul: src/ocr_engine.py
"""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from ocr_engine import (
    extract_text,
    _ensure_min_size,
    _is_garbage,
    _is_block_noise,
    _deskew,
    _morphological_cleanup,
    merge_text_blocks,
    TextBlock,
)


def _make_tesseract_data(
    words: list[str], confidences: list[int] | None = None
) -> dict:
    """Tesseract image_to_data çıktısını simüle eder."""
    if confidences is None:
        confidences = [80] * len(words)
    return {
        "text": words,
        "conf": confidences,
        "level": [5] * len(words),
        "page_num": [1] * len(words),
        "block_num": [1] * len(words),
        "par_num": [1] * len(words),
        "line_num": [1] * len(words),
        "word_num": list(range(1, len(words) + 1)),
        "left": [0] * len(words),
        "top": [0] * len(words),
        "width": [50] * len(words),
        "height": [20] * len(words),
    }


# ============================================================
# region _ensure_min_size Birim Testleri
# ============================================================


class TestEnsureMinSize:
    def test_buyuk_goruntu_degismez(self):
        img = np.zeros((100, 1500, 3), dtype=np.uint8)
        result = _ensure_min_size(img)
        assert result.shape == (100, 1500, 3)

    def test_kucuk_goruntu_olceklenir(self):
        img = np.zeros((50, 200, 3), dtype=np.uint8)
        result = _ensure_min_size(img)
        assert result.shape[1] >= 1200

    def test_tek_piksel_genislik(self):
        img = np.zeros((10, 1, 3), dtype=np.uint8)
        result = _ensure_min_size(img)
        assert result.shape[1] >= 1200

    def test_custom_target_width(self):
        img = np.zeros((100, 500, 3), dtype=np.uint8)
        result = _ensure_min_size(img, target_width=800)
        assert result.shape[1] >= 800


# ============================================================
# endregion
# ============================================================


# ============================================================
# region _deskew Birim Testleri
# ============================================================


class TestDeskew:
    def test_bos_goruntu_degismez(self):
        img = np.zeros((100, 100), dtype=np.uint8)
        result = _deskew(img)
        assert result.shape == img.shape

    def test_duz_metin_degismez(self):
        img = np.zeros((100, 200), dtype=np.uint8)
        img[40:60, 20:180] = 255  # Yatay beyaz cizgi
        result = _deskew(img)
        assert result.shape == img.shape


# ============================================================
# endregion
# ============================================================


# ============================================================
# region _morphological_cleanup Birim Testleri
# ============================================================


class TestMorphologicalCleanup:
    def test_binary_girdi_cikti(self):
        img = np.zeros((100, 100), dtype=np.uint8)
        img[30:70, 30:70] = 255
        result = _morphological_cleanup(img)
        assert result.shape == img.shape
        assert set(np.unique(result)).issubset({0, 255})

    def test_kucuk_noktalari_temizler(self):
        img = np.zeros((100, 100), dtype=np.uint8)
        img[10:12, 10:12] = 255  # 2x2 piksel gurultu
        img[50:80, 50:80] = 255  # Buyuk blok
        result = _morphological_cleanup(img)
        # Buyuk blok kalmali
        assert np.any(result[50:80, 50:80] > 0)


# ============================================================
# endregion
# ============================================================


# ============================================================
# region _is_garbage Birim Testleri
# ============================================================


class TestIsGarbage:
    def test_bos_metin_garbage(self):
        assert _is_garbage("") is True
        assert _is_garbage("   ") is True

    def test_tek_karakter_garbage(self):
        assert _is_garbage("a") is True

    def test_anlamli_metin_garbage_degil(self):
        assert _is_garbage("Hello World") is False

    def test_sadece_semboller_garbage(self):
        assert _is_garbage("@#$%^&*") is True

    def test_karisik_sembol_agirlikli_garbage(self):
        assert _is_garbage("e e 0 « 5 @ ¢ @ ~ 0O 0 0 0 = =") is True

    def test_dogal_dil_garbage_degil(self):
        assert _is_garbage("The quick brown fox jumps") is False

    def test_ocr_garbage_ornekleri(self):
        assert _is_garbage("KKCIANAATE APEGrant vitver Lt iy") is True
        assert _is_garbage("00QO0QO0POOOR o Q@ Qo X") is True
        assert _is_garbage("S 8 e 8 B 0 000 ~ B8 0 « O +") is True


# ============================================================
# endregion
# ============================================================


# ============================================================
# region _is_block_noise Birim Testleri
# ============================================================


class TestIsBlockNoise:
    def test_bos_metin_noise(self):
        assert _is_block_noise("") is True

    def test_tek_karakter_noise(self):
        assert _is_block_noise("a") is True

    def test_iki_karakter_noise(self):
        assert _is_block_noise("ab") is True

    def test_uc_karakter_dusuk_harf_noise(self):
        assert _is_block_noise("1@3") is True

    def test_uc_karakter_yuksek_harf_degil_noise(self):
        assert _is_block_noise("abc") is False

    def test_anlamli_metin_noise_degil(self):
        assert _is_block_noise("Hello World") is False


# ============================================================
# endregion
# ============================================================


# ============================================================
# region merge_text_blocks Birim Testleri
# ============================================================


class TestMergeTextBlocks:
    def test_bos_liste_bos_doner(self):
        assert merge_text_blocks([]) == []

    def test_tek_blok_ayni_doner(self):
        block = TextBlock(text="Hello", box=[0, 0, 100, 30], conf=0.9)
        result = merge_text_blocks([block])
        assert len(result) == 1
        assert result[0].text == "Hello"

    def test_yakin_bloklar_birlesir(self):
        blocks = [
            TextBlock(text="Hello", box=[0, 0, 50, 20], conf=0.9),
            TextBlock(text="World", box=[55, 0, 50, 20], conf=0.9),
        ]
        result = merge_text_blocks(blocks)
        assert len(result) == 1
        assert result[0].text == "Hello World"

    def test_uzak_bloklar_birlesmez(self):
        blocks = [
            TextBlock(text="Hello", box=[0, 0, 50, 20], conf=0.9),
            TextBlock(text="World", box=[500, 0, 50, 20], conf=0.9),
        ]
        result = merge_text_blocks(blocks)
        assert len(result) == 2

    def test_cok_kucuk_bloklar_filtrelenir(self):
        blocks = [
            TextBlock(text="ab", box=[0, 0, 5, 5], conf=0.9),
            TextBlock(text="Hello World", box=[0, 50, 200, 30], conf=0.9),
        ]
        result = merge_text_blocks(blocks)
        # 5x5 blok filtrelenmeli (min_w=20, min_h=10)
        assert all(b.box[2] >= 20 for b in result)


# ============================================================
# endregion
# ============================================================


# ============================================================
# region TextBlock Birim Testleri
# ============================================================


class TestTextBlock:
    def test_olusturma(self):
        block = TextBlock(text="Test", box=[0, 0, 100, 30], conf=0.85)
        assert block.text == "Test"
        assert block.box == [0, 0, 100, 30]
        assert block.conf == 0.85


# ============================================================
# endregion
# ============================================================
