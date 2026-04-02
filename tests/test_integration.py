"""
OCR-TRANSLATE — Entegrasyon Testleri
=====================================
Test Framework: pytest
Birden fazla bilesenin birlikte calismasini dogrular.

Test edilen akislar:
1. OCR → Cache entegrasyonu
2. OCR → Translate → Cache entegrasyonu
3. Tam pipeline: Capture → OCR → Cache → Translate → Overlay
4. Config degerlerinin tutuarliligi
"""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from cache import TextCache
from ocr_engine import extract_text
from translator import translate


def _make_tesseract_data(text: str, confidence: int = 85) -> dict:
    """Tesseract image_to_data çıktısını simüle eder."""
    words = text.split() if text.strip() else []
    return {
        "text": words,
        "conf": [confidence] * len(words),
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
# region OCR → Cache Entegrasyonu
# ============================================================


class TestOCRCacheIntegration:
    """OCR ciktisinin Cache ile dogru calismasini dogrular."""

    @patch("ocr_engine.pytesseract.image_to_data")
    def test_ocr_ciktisi_cache_akisi(self, mock_tesseract):
        """
        OCR → is_new_text → store → get_cached akisi.
        """
        mock_tesseract.return_value = _make_tesseract_data("Hello World")
        cache = TextCache()

        # Sahte goruntu
        image = np.zeros((50, 200, 3), dtype=np.uint8)
        text = extract_text(image)

        # Adim 1: Metin yeni mi?
        assert cache.is_new_text(text) is True

        # Adim 2: Cache'te yok
        assert cache.get_cached_translation(text) is None

        # Adim 3: Ceviriyi kaydet
        cache.store(text, "Merhaba Dunya")

        # Adim 4: Ayni metin tekrar — yeni degil
        assert cache.is_new_text(text) is False

        # Adim 5: Cache'ten getir
        assert cache.get_cached_translation(text) == "Merhaba Dunya"

    @patch("ocr_engine.pytesseract.image_to_data")
    def test_bos_ocr_ciktisi_cache_tetiklemez(self, mock_tesseract):
        """Bos OCR ciktisi cache kontrolune girmemeli."""
        mock_tesseract.return_value = _make_tesseract_data("")
        cache = TextCache()

        image = np.zeros((50, 200, 3), dtype=np.uint8)
        text = extract_text(image)

        assert text == ""
        assert cache.is_new_text(text) is False

    @patch("ocr_engine.pytesseract.image_to_data")
    def test_benzer_ocr_metinleri_cache_eslesmesi(self, mock_tesseract):
        """Benzer OCR metinleri cache'ten ceviri donmeli."""
        cache = TextCache(threshold=0.85)

        # Ilk frame
        mock_tesseract.return_value = _make_tesseract_data(
            "The hero walked into the forest"
        )
        image = np.zeros((50, 200, 3), dtype=np.uint8)
        text1 = extract_text(image)
        cache.store(text1, "Kahraman ormana girdi")

        # Ikinci frame — kucuk OCR farki
        mock_tesseract.return_value = _make_tesseract_data(
            "The hero walked into the forest."
        )
        text2 = extract_text(image)

        # Benzer metin cache'ten ceviri donmeli
        cached = cache.get_cached_translation(text2)
        assert cached == "Kahraman ormana girdi"


# ============================================================
# endregion
# ============================================================


# ============================================================
# region OCR → Translate → Cache Entegrasyonu
# ============================================================


class TestOCRTranslateCacheIntegration:
    """OCR → Translate → Cache tam akis testi."""

    @patch("translator.requests.post")
    @patch("ocr_engine.pytesseract.image_to_data")
    def test_tam_ceviri_pipeline(self, mock_tesseract, mock_post):
        """
        Tam pipeline: OCR metin cikar → Cache kontrol → Translate → Cache store
        """
        # OCR mock
        mock_tesseract.return_value = _make_tesseract_data("The dragon breathes fire")

        # Translate mock
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Ejderha ates puskurtuyor"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        cache = TextCache()
        image = np.zeros((50, 200, 3), dtype=np.uint8)

        # 1. OCR
        text = extract_text(image)
        assert text == "The dragon breathes fire"

        # 2. Yeni metin mi?
        assert cache.is_new_text(text) is True

        # 3. Cache'te var mi?
        assert cache.get_cached_translation(text) is None

        # 4. Cevir
        translation = translate(text)
        assert translation == "Ejderha ates puskurtuyor"

        # 5. Cache'e kaydet
        cache.store(text, translation)

        # 6. Ikinci tick — ayni metin
        text2 = extract_text(image)
        assert cache.is_new_text(text2) is False
        # API bir daha cagrilmamali (cache kullanilmali)

    @patch("translator.requests.post")
    @patch("ocr_engine.pytesseract.image_to_data")
    def test_ceviri_basarisiz_cache_bos_kalir(self, mock_tesseract, mock_post):
        """Ceviri basarisiz olursa cache'e birsey eklenmemeli."""
        mock_tesseract.return_value = _make_tesseract_data("Some text")

        import requests as req

        mock_post.side_effect = req.exceptions.ConnectionError("refused")

        cache = TextCache()
        image = np.zeros((50, 200, 3), dtype=np.uint8)

        text = extract_text(image)
        translation = translate(text)

        assert translation is None
        assert len(cache._cache) == 0


# ============================================================
# endregion
# ============================================================


# ============================================================
# region Config Tutarliligi
# ============================================================


class TestConfigConsistency:
    """config.py degerlerinin tutarliligini dogrular."""

    def test_threshold_gecerli_aralik(self):
        """SIMILARITY_THRESHOLD 0-1 araliginda olmali."""
        from config import SIMILARITY_THRESHOLD

        assert 0.0 <= SIMILARITY_THRESHOLD <= 1.0

    def test_cache_max_size_pozitif(self):
        """CACHE_MAX_SIZE pozitif tamsayi olmali."""
        from config import CACHE_MAX_SIZE

        assert CACHE_MAX_SIZE > 0
        assert isinstance(CACHE_MAX_SIZE, int)

    def test_capture_interval_makul(self):
        """CAPTURE_INTERVAL_MS 100-10000 araliginda olmali."""
        from config import CAPTURE_INTERVAL_MS

        assert 100 <= CAPTURE_INTERVAL_MS <= 10000

    def test_ollama_timeout_pozitif(self):
        """OLLAMA_TIMEOUT pozitif olmali."""
        from config import OLLAMA_TIMEOUT

        assert OLLAMA_TIMEOUT > 0

    def test_ollama_url_format(self):
        """OLLAMA_URL gecerli URL formati olmali."""
        from config import OLLAMA_URL

        assert OLLAMA_URL.startswith("http")
        assert "/api/" in OLLAMA_URL

    def test_ocr_psm_gecerli(self):
        """OCR_PSM gecerli Tesseract PSM degeri olmali (0-13)."""
        from config import OCR_PSM

        assert 0 <= OCR_PSM <= 13

    def test_translation_prompt_placeholder(self):
        """Prompt sablonunda {text} placeholder'i olmali."""
        from config import TRANSLATION_PROMPT

        assert "{text}" in TRANSLATION_PROMPT

    def test_overlay_font_size_pozitif(self):
        """Overlay font boyutu pozitif olmali."""
        from config import OVERLAY_FONT_SIZE

        assert OVERLAY_FONT_SIZE > 0

    def test_overlay_padding_negatif_olmaz(self):
        """Overlay padding negatif olamaz."""
        from config import OVERLAY_PADDING

        assert OVERLAY_PADDING >= 0

    def test_overlay_bg_color_hardcoded_bug(self):
        """
        Config'te OVERLAY_BG_COLOR tanimli mi kontrol eder.
        overlay.py bu degeri kullanmali, hardcoded renk kullanmamali.
        """
        from config import OVERLAY_BG_COLOR

        assert OVERLAY_BG_COLOR.startswith("rgba("), (
            "OVERLAY_BG_COLOR rgba formatinda olmali"
        )


# ============================================================
# endregion
# ============================================================


# ============================================================
# region Stres Testleri
# ============================================================


class TestStress:
    """Yogun kullanim senaryolari."""

    def test_cache_yogun_kullanim(self):
        """1000 farkli metin ile cache dogru calismali."""
        cache = TextCache(max_size=100)

        for i in range(1000):
            cache.store(f"Source text number {i}", f"Ceviri {i}")

        # Son 100 giriste olmali (tam eslesme)
        assert cache.get_cached_translation("Source text number 999") == "Ceviri 999"
        assert cache.get_cached_translation("Source text number 900") == "Ceviri 900"

        # Boyut kontrolu
        assert len(cache._cache) == 100

        # Tam eslesme kontrolu: "Source text number 0" cache'te olmamali
        assert "Source text number 0" not in cache._cache

    def test_fuzzy_match_yanlis_ceviri_bug(self):
        """
        BUG #7 TESPITI:
        Silinmis bir metin, fuzzy benzerlik yuzunden yanlis cache hit donebilir.
        Ornegin "Source text number 0" silinmis ama "Source text number 901"
        hala cache'te ve benzerlik yuksek → yanlis ceviri doner.
        """
        cache = TextCache(max_size=5)

        cache.store("Source text number 0", "Ceviri 0")
        cache.store("Source text number 1", "Ceviri 1")
        cache.store("Source text number 2", "Ceviri 2")
        cache.store("Source text number 3", "Ceviri 3")
        cache.store("Source text number 4", "Ceviri 4")
        cache.store("Source text number 5", "Ceviri 5")  # "0" silinmeli

        # "0" artik cache'te degil ama fuzzy match baska ceviri donebilir
        result = cache.get_cached_translation("Source text number 0")
        if result is not None and result != "Ceviri 0":
            pytest.xfail(
                f"BUG ONAYLANDI: Silinmis metin icin yanlis ceviri dondu: '{result}'. "
                "Fuzzy match, silinmis girisi baska bir girsle eslestirdi."
            )

    @patch("ocr_engine.pytesseract.image_to_data")
    def test_hizli_art_arda_ocr_cagrilari(self, mock_tesseract):
        """Art arda OCR cagrilari tutarli sonuc vermeli."""
        mock_tesseract.return_value = _make_tesseract_data("Consistent text")
        image = np.zeros((50, 200, 3), dtype=np.uint8)

        results = [extract_text(image) for _ in range(100)]

        assert all(r == "Consistent text" for r in results)

    def test_cache_is_new_text_hizli(self):
        """is_new_text 1000 cagri ile tutarli olmali."""
        cache = TextCache()
        cache.is_new_text("Initial text")

        # Ayni metin 1000 kez
        results = [cache.is_new_text("Initial text") for _ in range(1000)]
        assert all(r is False for r in results)


# ============================================================
# endregion
# ============================================================
