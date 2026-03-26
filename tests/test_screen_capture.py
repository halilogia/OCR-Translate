"""
OCR-TRANSLATE — Screen Capture Birim & Kenar Durum Testleri
============================================================
Test Framework: pytest
Dogruladigi Modul: src/screen_capture.py

Tespit edilen olasi hatalar:
- BUG #3 (KRITIK - devam): capture_region() BGRA → [:, :, :3] yapar.
  Bu BGR verir, RGB degil. Yorum satirinda "RGB'ye cevir" yaziyor ama
  aslinda BGR donuyor. ocr_engine.py COLOR_RGB2GRAY ile islerken
  yanlis kanal sirasi kullanir.
- BUG #5: Region TypedDict'i mss.grab()'in bekledigini tip ile
  uyumsuz olabilir (TypedDict vs dict).
"""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from screen_capture import (
    Region,
    capture_region,
    capture_full_screen,
    get_full_screen_region,
)


# ============================================================
# region Region TypedDict Testleri
# ============================================================


class TestRegion:
    """Region TypedDict yapisal testleri."""

    def test_gecerli_region_olusturma(self):
        """Gecerli Region dict olusturulabilmeli."""
        region = Region(top=0, left=0, width=800, height=600)
        assert region["top"] == 0
        assert region["left"] == 0
        assert region["width"] == 800
        assert region["height"] == 600

    def test_region_tum_anahtarlar(self):
        """Region 4 zorunlu anahtara sahip olmali."""
        region = Region(top=100, left=200, width=300, height=400)
        required_keys = {"top", "left", "width", "height"}
        assert required_keys == set(region.keys())


# ============================================================
# endregion
# ============================================================


# ============================================================
# region capture_region() Testleri
# ============================================================


class TestCaptureRegion:
    """capture_region() fonksiyonu testleri."""

    @patch("screen_capture.mss.mss")
    def test_donus_tipi_numpy(self, mock_mss, sample_region):
        """Donen deger numpy ndarray olmali."""
        # BGRA mock goruntu
        mock_screenshot = MagicMock()
        bgra_data = np.zeros((100, 800, 4), dtype=np.uint8)
        # numpy array'e cevirme mock'u
        mock_sct = MagicMock()
        mock_sct.grab.return_value = mock_screenshot
        mock_mss.return_value.__enter__ = MagicMock(return_value=mock_sct)
        mock_mss.return_value.__exit__ = MagicMock(return_value=False)

        with patch("numpy.array", return_value=bgra_data):
            result = capture_region(sample_region)

        assert isinstance(result, np.ndarray)

    @patch("screen_capture.mss.mss")
    def test_alpha_kanali_atilir(self, mock_mss, sample_region):
        """BGRA'dan alpha kanali atilip 3 kanal donmeli."""
        bgra_data = np.zeros((100, 800, 4), dtype=np.uint8)
        bgra_data[:, :, 3] = 255  # Alpha

        mock_sct = MagicMock()
        mock_sct.grab.return_value = MagicMock()
        mock_mss.return_value.__enter__ = MagicMock(return_value=mock_sct)
        mock_mss.return_value.__exit__ = MagicMock(return_value=False)

        with patch("numpy.array", return_value=bgra_data):
            result = capture_region(sample_region)

        assert result.shape[2] == 3, f"3 kanal olmali ama {result.shape[2]} kanal var"

    @patch("screen_capture.mss.mss")
    def test_bgr_vs_rgb_kanal_sirasi(self, mock_mss, sample_region):
        """
        BUG #3 TESPITI:
        mss BGRA doner. [:, :, :3] uygulaninca BGR kalir.
        Yorum 'RGB'ye cevir' diyor ama aslinda BGR.

        Bu test BUG'u kanitlar:
        BGRA(B=100, G=50, R=200, A=255) → [:,:,:3] → (100, 50, 200) = BGR
        RGB olsaydi (200, 50, 100) olmali.
        """
        # Bilinen degerlerle BGRA goruntu
        bgra_data = np.zeros((1, 1, 4), dtype=np.uint8)
        bgra_data[0, 0] = [100, 50, 200, 255]  # B=100, G=50, R=200, A=255

        mock_sct = MagicMock()
        mock_sct.grab.return_value = MagicMock()
        mock_mss.return_value.__enter__ = MagicMock(return_value=mock_sct)
        mock_mss.return_value.__exit__ = MagicMock(return_value=False)

        with patch("numpy.array", return_value=bgra_data):
            result = capture_region(sample_region)

        # [:, :, :3] → ilk 3 kanal = BGR
        b, g, r = result[0, 0]

        if b == 100 and r == 200:
            # BGR dondugu dogrulandi — bu BUG
            pytest.xfail(
                "BUG ONAYLANDI: capture_region BGR donuyor, RGB degil. "
                "frame[:, :, :3] sadece alpha kanali atiyor, "
                "BGR→RGB donusumu yapmiyor. "
                "COZUM: frame[:, :, :3][:, :, ::-1] veya "
                "cv2.cvtColor(frame[:, :, :3], cv2.COLOR_BGR2RGB) kullanilmali."
            )


# ============================================================
# endregion
# ============================================================


# ============================================================
# region capture_full_screen() Testleri
# ============================================================


class TestCaptureFullScreen:
    """capture_full_screen() testleri."""

    @patch("screen_capture.mss.mss")
    def test_tum_ekran_yakalama(self, mock_mss):
        """Tam ekran goruntusunu donmeli."""
        bgra_data = np.zeros((1080, 1920, 4), dtype=np.uint8)

        mock_sct = MagicMock()
        mock_sct.monitors = [{"top": 0, "left": 0, "width": 1920, "height": 1080}]
        mock_sct.grab.return_value = MagicMock()
        mock_mss.return_value.__enter__ = MagicMock(return_value=mock_sct)
        mock_mss.return_value.__exit__ = MagicMock(return_value=False)

        with patch("numpy.array", return_value=bgra_data):
            result = capture_full_screen()

        assert result.shape[2] == 3

    @patch("screen_capture.mss.mss")
    def test_monitors_0_kullanilir(self, mock_mss):
        """monitors[0] (sanal ekran) kullanilmali."""
        bgra_data = np.zeros((100, 100, 4), dtype=np.uint8)

        mock_sct = MagicMock()
        mock_sct.monitors = [
            {"top": 0, "left": 0, "width": 3840, "height": 1080},  # Sanal (tum)
            {"top": 0, "left": 0, "width": 1920, "height": 1080},  # Monitor 1
            {"top": 0, "left": 1920, "width": 1920, "height": 1080},  # Monitor 2
        ]
        mock_sct.grab.return_value = MagicMock()
        mock_mss.return_value.__enter__ = MagicMock(return_value=mock_sct)
        mock_mss.return_value.__exit__ = MagicMock(return_value=False)

        with patch("numpy.array", return_value=bgra_data):
            capture_full_screen()

        # monitors[0] kullanildi mi?
        grab_arg = mock_sct.grab.call_args[0][0]
        assert grab_arg["width"] == 3840


# ============================================================
# endregion
# ============================================================


# ============================================================
# region get_full_screen_region() Testleri
# ============================================================


class TestGetFullScreenRegion:
    """get_full_screen_region() testleri."""

    @patch("screen_capture.mss.mss")
    def test_region_dict_donmeli(self, mock_mss):
        """Region dict donmeli."""
        mock_sct = MagicMock()
        mock_sct.monitors = [{"top": 0, "left": 0, "width": 1920, "height": 1080}]
        mock_mss.return_value.__enter__ = MagicMock(return_value=mock_sct)
        mock_mss.return_value.__exit__ = MagicMock(return_value=False)

        region = get_full_screen_region()

        assert "top" in region
        assert "left" in region
        assert "width" in region
        assert "height" in region

    @patch("screen_capture.mss.mss")
    def test_dogru_degerler(self, mock_mss):
        """Monitor degerlerini dogru donmeli."""
        mock_sct = MagicMock()
        mock_sct.monitors = [{"top": 10, "left": 20, "width": 2560, "height": 1440}]
        mock_mss.return_value.__enter__ = MagicMock(return_value=mock_sct)
        mock_mss.return_value.__exit__ = MagicMock(return_value=False)

        region = get_full_screen_region()

        assert region["top"] == 10
        assert region["left"] == 20
        assert region["width"] == 2560
        assert region["height"] == 1440


# ============================================================
# endregion
# ============================================================
