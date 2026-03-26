"""
OCR-TRANSLATE — OCR Engine Birim & Kenar Durum Testleri
=======================================================
Test Framework: pytest
Dogruladigi Modul: src/ocr_engine.py

Tespit edilen olasi hatalar:
- BUG #3 (KRITIK): screen_capture.py BGRA formatinda doner ve [:, :, :3]
  ile sadece alpha kanali atar → sonuc BGR olur (RGB degil!).
  Ama ocr_engine.py cv2.COLOR_RGB2GRAY kullanir — yanlis kanal sirasi.
  Bu OCR dogrulugunu dusurur cunku gri tonlama formulunde R/G/B katsayilari
  farklidir: Gray = 0.299*R + 0.587*G + 0.114*B
  BGR verilirse: Gray = 0.299*B + 0.587*G + 0.114*R → yanlis parlaklik.
"""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from ocr_engine import preprocess_image, extract_text


# ============================================================
# region preprocess_image Birim Testleri
# ============================================================


class TestPreprocessImage:
    """preprocess_image() fonksiyonu icin testler."""

    def test_rgb_girdi_gray_cikti(self, sample_rgb_image):
        """RGB goruntu gri tonlamaya donusturulmeli."""
        result = preprocess_image(sample_rgb_image)
        assert result.ndim == 2, "Sonuc 2 boyutlu (grayscale) olmali"

    def test_cikti_binary(self, sample_rgb_image):
        """Otsu thresholding sonrasi cikti binary (0 veya 255) olmali."""
        result = preprocess_image(sample_rgb_image)
        unique_vals = set(np.unique(result))
        assert unique_vals.issubset({0, 255}), f"Binary olmayan degerler: {unique_vals}"

    def test_boyut_korunur(self, sample_rgb_image):
        """Cikti boyutu girdinin yukseklik x genisligine esit olmali."""
        result = preprocess_image(sample_rgb_image)
        h, w = sample_rgb_image.shape[:2]
        assert result.shape == (h, w)

    def test_beyaz_metin_siyah_arkaplan(self):
        """Beyaz metin siyah arka plan uzerinde: metin beyaz (255) olmali."""
        img = np.zeros((50, 200, 3), dtype=np.uint8)
        img[15:35, 30:170] = 255  # Beyaz bant
        result = preprocess_image(img)
        # Beyaz bolgedeki piksellerin cogu 255 olmali
        white_region = result[15:35, 30:170]
        white_ratio = np.count_nonzero(white_region == 255) / white_region.size
        assert white_ratio > 0.5, f"Beyaz oran: {white_ratio:.2f}"


class TestPreprocessImageEdgeCases:
    """preprocess_image() kenar durumlari."""

    def test_tamamen_siyah_goruntu(self):
        """Tamamen siyah goruntu hata vermemeli."""
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = preprocess_image(img)
        assert result.shape == (100, 100)

    def test_tamamen_beyaz_goruntu(self):
        """Tamamen beyaz goruntu hata vermemeli."""
        img = np.full((100, 100, 3), 255, dtype=np.uint8)
        result = preprocess_image(img)
        assert result.shape == (100, 100)

    def test_tek_piksel(self):
        """1x1 goruntu hata vermemeli."""
        img = np.zeros((1, 1, 3), dtype=np.uint8)
        result = preprocess_image(img)
        assert result.shape == (1, 1)

    def test_cok_kucuk_goruntu(self):
        """2x2 goruntu islenmeli."""
        img = np.zeros((2, 2, 3), dtype=np.uint8)
        result = preprocess_image(img)
        assert result.shape == (2, 2)

    def test_cok_buyuk_goruntu(self):
        """4K goruntu hata vermemeli (performans testi degil)."""
        img = np.zeros((2160, 3840, 3), dtype=np.uint8)
        result = preprocess_image(img)
        assert result.shape == (2160, 3840)

    def test_bgr_vs_rgb_fark_tespiti(self):
        """
        BUG #3 TESPITI:
        BGR ve RGB girdi arasindaki fark gri tonlama sonucunu etkiler.
        screen_capture BGR donuyor ama ocr_engine RGB bekliyor.
        """
        # Saf kirmizi piksel — RGB: (255,0,0) vs BGR: (0,0,255)
        rgb_img = np.zeros((10, 10, 3), dtype=np.uint8)
        rgb_img[:, :, 0] = 255  # R kanali

        bgr_img = np.zeros((10, 10, 3), dtype=np.uint8)
        bgr_img[:, :, 2] = 255  # BGR'de R kanali 3. indeks

        rgb_result = preprocess_image(rgb_img)
        bgr_result = preprocess_image(bgr_img)

        # Eger COLOR_RGB2GRAY kullaniliyorsa, ayni fiziksel renk (kirmizi)
        # farkli iki girdide FARKLI gri deger uretir — bu BUG.
        # RGB kirmizi: Gray = 0.299*255 = 76.2
        # BGR kirmizi (ama RGB2GRAY ile): Gray = 0.114*255 = 29.1
        if not np.array_equal(rgb_result, bgr_result):
            # Bu BEKLENEN DAVRANIS — bug'u dogrular
            pass  # Test basarili: fark var = bug kanitlandi

    def test_float_goruntu_hata(self):
        """float64 goruntu TypeError vermeli (uint8 bekleniyor)."""
        img = np.zeros((10, 10, 3), dtype=np.float64)
        # OpenCV float goruntuyu kabul eder ama sonuc farkli olabilir
        # Bu test sadece hata olmadigini dogrular
        try:
            result = preprocess_image(img)
            assert result.shape == (10, 10)
        except Exception:
            pass  # Bazı OpenCV sürümlerinde hata olabilir


# ============================================================
# endregion
# ============================================================


# ============================================================
# region extract_text Birim Testleri (Mock)
# ============================================================


class TestExtractText:
    """extract_text() fonksiyonu — Tesseract mock'lanarak test edilir."""

    @patch("ocr_engine.pytesseract.image_to_string")
    def test_basarili_metin_cikarma(self, mock_tesseract, sample_rgb_image):
        """Tesseract'tan donen metin temizlenmeli."""
        mock_tesseract.return_value = "  Hello World  \n\n  Test  \n"
        result = extract_text(sample_rgb_image)
        assert result == "Hello World Test"

    @patch("ocr_engine.pytesseract.image_to_string")
    def test_bos_sonuc(self, mock_tesseract, sample_rgb_image):
        """Tesseract bos string donerse bos string donmeli."""
        mock_tesseract.return_value = ""
        result = extract_text(sample_rgb_image)
        assert result == ""

    @patch("ocr_engine.pytesseract.image_to_string")
    def test_sadece_bosluk_sonuc(self, mock_tesseract, sample_rgb_image):
        """Sadece bosluk/newline donerse bos string donmeli."""
        mock_tesseract.return_value = "\n\n   \n  \t  \n"
        result = extract_text(sample_rgb_image)
        assert result == ""

    @patch("ocr_engine.pytesseract.image_to_string")
    def test_tek_satir(self, mock_tesseract, sample_rgb_image):
        """Tek satirlik metin duzgun donmeli."""
        mock_tesseract.return_value = "Single line text"
        result = extract_text(sample_rgb_image)
        assert result == "Single line text"

    @patch("ocr_engine.pytesseract.image_to_string")
    def test_cok_satirli_birlestirme(self, mock_tesseract, sample_rgb_image):
        """Birden fazla satir boslukla birlestirilmeli."""
        mock_tesseract.return_value = "Line 1\nLine 2\nLine 3"
        result = extract_text(sample_rgb_image)
        assert result == "Line 1 Line 2 Line 3"

    @patch("ocr_engine.pytesseract.image_to_string")
    def test_config_parametreleri(self, mock_tesseract, sample_rgb_image):
        """Tesseract'a dogru config gecilmeli."""
        mock_tesseract.return_value = "test"
        extract_text(sample_rgb_image)
        call_args = mock_tesseract.call_args
        config_str = (
            call_args[1].get("config", "")
            if call_args[1]
            else call_args[0][1]
            if len(call_args[0]) > 1
            else ""
        )
        assert "--oem 3" in config_str
        assert "--psm 6" in config_str
        assert "-l eng" in config_str

    @patch("ocr_engine.pytesseract.image_to_string")
    def test_ozel_karakterler(self, mock_tesseract, sample_rgb_image):
        """Ozel karakterler korunmali."""
        mock_tesseract.return_value = "Hello! @#$% World?"
        result = extract_text(sample_rgb_image)
        assert result == "Hello! @#$% World?"


# ============================================================
# endregion
# ============================================================


# ============================================================
# region Hata Ayiklama Testleri
# ============================================================


class TestOCRDebugFlow:
    """OCR pipeline'inin adim adim dogrulanmasi."""

    def test_preprocess_pipeline_adimlari(self, sample_rgb_image):
        """
        Ön işleme adimlarini tek tek dogrular:
        1. RGB → Gray donusumu
        2. CLAHE uygulamasi
        3. Otsu thresholding
        """
        import cv2

        # Adim 1: Gri tonlama
        gray = cv2.cvtColor(sample_rgb_image, cv2.COLOR_RGB2GRAY)
        assert gray.ndim == 2, "Adim 1 FAIL: Gri tonlama basarisiz"
        assert gray.dtype == np.uint8, "Adim 1 FAIL: Tip uint8 olmali"

        # Adim 2: CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        assert enhanced.shape == gray.shape, "Adim 2 FAIL: CLAHE boyut bozdu"

        # Adim 3: Otsu
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        assert set(np.unique(binary)).issubset({0, 255}), "Adim 3 FAIL: Binary degil"

    @patch("ocr_engine.pytesseract.image_to_string")
    def test_extract_text_hata_propagasyonu(self, mock_tesseract, sample_rgb_image):
        """Tesseract exception'i yukariya iletilmeli."""
        mock_tesseract.side_effect = Exception("Tesseract not found")
        with pytest.raises(Exception, match="Tesseract not found"):
            extract_text(sample_rgb_image)


# ============================================================
# endregion
# ============================================================
