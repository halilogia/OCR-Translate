"""
OCR-TRANSLATE — Translator Birim & Kenar Durum Testleri
=======================================================
Test Framework: pytest
Dogruladigi Modul: src/translator.py

Tespit edilen olasi sorunlar:
- BUG #4: check_ollama_connection model adini normalize ederken
  tag'li ve tag'siz modelleri eslestirir ama "gemma3:4b" ile "gemma3:latest"
  gibi farkli tag'li modeller yanlis eslesebilir.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from translator import translate, check_ollama_connection


# ============================================================
# region translate() Birim Testleri
# ============================================================


class TestTranslate:
    """translate() fonksiyonu birim testleri."""

    @patch("translator.requests.post")
    def test_basarili_ceviri(self, mock_post):
        """Basarili Ollama yaniti dogru ceviriyi donmeli."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Merhaba Dunya"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = translate("Hello World")
        assert result == "Merhaba Dunya"

    @patch("translator.requests.post")
    def test_bos_girdi_none_doner(self, mock_post):
        """Bos girdi None donmeli, API cagrilmamali."""
        result = translate("")
        assert result is None
        mock_post.assert_not_called()

    @patch("translator.requests.post")
    def test_bosluk_girdi_none_doner(self, mock_post):
        """Sadece bosluk iceren girdi None donmeli."""
        result = translate("   \n\t  ")
        assert result is None
        mock_post.assert_not_called()

    @patch("translator.requests.post")
    def test_bos_yanit_none_doner(self, mock_post):
        """Ollama bos yanit donerse None donmeli."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": ""}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = translate("Hello")
        assert result is None

    @patch("translator.requests.post")
    def test_sadece_bosluk_yanit_none_doner(self, mock_post):
        """Ollama sadece bosluk donerse None donmeli."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "   \n  "}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = translate("Hello")
        assert result is None

    @patch("translator.requests.post")
    def test_model_parametresi(self, mock_post):
        """Farkli model belirtilebilmeli."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Test"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        translate("Hello", model="llama3:8b")

        call_data = mock_post.call_args[1]["json"]
        assert call_data["model"] == "llama3:8b"

    @patch("translator.requests.post")
    def test_prompt_format(self, mock_post):
        """Prompt sablonu dogru doldurulmali."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Test"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        translate("Hello World")

        call_data = mock_post.call_args[1]["json"]
        assert "Hello World" in call_data["prompt"]
        assert "Translate" in call_data["prompt"]
        assert "Turkish" in call_data["prompt"]

    @patch("translator.requests.post")
    def test_api_parametreleri(self, mock_post):
        """Temperature ve num_predict dogru gonderilmeli."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Test"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        translate("Test")

        call_data = mock_post.call_args[1]["json"]
        assert call_data["stream"] is False
        assert call_data["options"]["temperature"] == 0.3
        assert call_data["options"]["num_predict"] == 256


# ============================================================
# endregion
# ============================================================


# ============================================================
# region translate() Hata Durumu Testleri
# ============================================================


class TestTranslateErrors:
    """translate() hata yonetimi testleri."""

    @patch("translator.requests.post")
    def test_connection_error_none_doner(self, mock_post):
        """ConnectionError'da None donmeli (exception firlatilmamali)."""
        import requests

        mock_post.side_effect = requests.exceptions.ConnectionError(
            "Connection refused"
        )
        result = translate("Hello")
        assert result is None

    @patch("translator.requests.post")
    def test_timeout_error_none_doner(self, mock_post):
        """Timeout'da None donmeli."""
        import requests

        mock_post.side_effect = requests.exceptions.Timeout("Timeout")
        result = translate("Hello")
        assert result is None

    @patch("translator.requests.post")
    def test_http_error_none_doner(self, mock_post):
        """HTTP 500 gibi hatalarda None donmeli."""
        import requests

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500"
        )
        mock_post.return_value = mock_response
        result = translate("Hello")
        assert result is None

    @patch("translator.requests.post")
    def test_json_decode_error_none_doner(self, mock_post):
        """Gecersiz JSON yanitinda None donmeli."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = json.JSONDecodeError("err", "", 0)
        mock_post.return_value = mock_response
        result = translate("Hello")
        assert result is None

    @patch("translator.requests.post")
    def test_response_key_eksik_none_doner(self, mock_post):
        """'response' anahtari yoksa bos string → None donmeli."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"model": "gemma3", "done": True}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        result = translate("Hello")
        assert result is None


# ============================================================
# endregion
# ============================================================


# ============================================================
# region translate() Kenar Durumlari
# ============================================================


class TestTranslateEdgeCases:
    """translate() kenar durum testleri."""

    @patch("translator.requests.post")
    def test_cok_uzun_metin(self, mock_post):
        """Cok uzun metin hata vermemeli."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Ceviri"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        long_text = "Hello world. " * 1000
        result = translate(long_text)
        assert result == "Ceviri"

    @patch("translator.requests.post")
    def test_unicode_metin(self, mock_post):
        """Unicode icerikli metin islenmeli."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Ceviri sonucu"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = translate("Cafe resume naïve")
        assert result == "Ceviri sonucu"

    @patch("translator.requests.post")
    def test_ozel_karakter_metin(self, mock_post):
        """Ozel karakterler prompt'u bozmamalı."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Test"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = translate('He said "Hello" & {goodbye}')
        assert result is not None

    @patch("translator.requests.post")
    def test_strip_uygulanir(self, mock_post):
        """Girdi ve cikti striplenmeli."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "  Merhaba  "}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = translate("  Hello  ")
        assert result == "Merhaba"
        # Prompt'taki metin de stripli olmali
        call_data = mock_post.call_args[1]["json"]
        assert "  Hello  " not in call_data["prompt"]
        assert "Hello" in call_data["prompt"]


# ============================================================
# endregion
# ============================================================


# ============================================================
# region check_ollama_connection() Testleri
# ============================================================


class TestCheckOllamaConnection:
    """check_ollama_connection() fonksiyonu testleri."""

    @patch("translator.requests.get")
    def test_baglanti_basarili_model_mevcut(self, mock_get):
        """Servis aktif ve model mevcutsa True donmeli."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "gemma3:4b"},
                {"name": "llama3:8b"},
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        assert check_ollama_connection("gemma3:4b") is True

    @patch("translator.requests.get")
    def test_model_bulunamadi(self, mock_get):
        """Servis aktif ama model yoksa False donmeli."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3:8b"},
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        assert check_ollama_connection("gemma3:4b") is False

    @patch("translator.requests.get")
    def test_model_adi_normalizasyonu(self, mock_get):
        """Tag olmadan model adi eslestirilmeli (gemma3 → gemma3:4b)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "gemma3:4b"},
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # "gemma3" sorgusu "gemma3:4b" ile eslesmeli
        assert check_ollama_connection("gemma3") is True

    @patch("translator.requests.get")
    def test_bos_model_listesi(self, mock_get):
        """Model listesi bossa False donmeli."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        assert check_ollama_connection("gemma3:4b") is False

    @patch("translator.requests.get")
    def test_connection_error(self, mock_get):
        """Baglanti hatasinda False donmeli."""
        import requests

        mock_get.side_effect = requests.exceptions.ConnectionError("refused")
        assert check_ollama_connection() is False

    @patch("translator.requests.get")
    def test_timeout_error(self, mock_get):
        """Zaman asiminda False donmeli."""
        import requests

        mock_get.side_effect = requests.exceptions.Timeout("timeout")
        assert check_ollama_connection() is False

    @patch("translator.requests.get")
    def test_base_url_dogru_olusturulur(self, mock_get):
        """API URL'den base URL dogru cikarilmali."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "test:latest"}]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        check_ollama_connection("test")

        called_url = mock_get.call_args[0][0]
        assert "/api/tags" in called_url
        assert "/api/generate" not in called_url

    @patch("translator.requests.get")
    def test_yanlis_tag_eslesmesi(self, mock_get):
        """
        BUG #4 TESPITI:
        'gemma3' sorgusu 'gemma3:latest' ile de eslesir.
        Kullanici 'gemma3:4b' istiyorsa bu yanlis olabilir.
        """
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "gemma3:latest"},  # 4b degil, latest
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # "gemma3:4b" araniyor ama "gemma3:latest" var
        # model_base = "gemma3", startswith("gemma3:") → True
        # BUG: Farkli tag'li model eslesir
        result = check_ollama_connection("gemma3:4b")
        if result is True:
            pytest.xfail(
                "BUG ONAYLANDI: gemma3:4b arandi ama gemma3:latest eslesti. "
                "Tag-specific eslesme yapilmiyor."
            )


# ============================================================
# endregion
# ============================================================


# ============================================================
# region Hata Ayiklama (Debug) Testleri
# ============================================================


class TestTranslatorDebugFlow:
    """Ceviri akisini adim adim dogrulamak icin debug testleri."""

    @patch("translator.requests.post")
    def test_tam_ceviri_akisi(self, mock_post):
        """
        1. Metin temizlenmeli
        2. Prompt olusturulmali
        3. API cagrilmali
        4. Yanit parse edilmeli
        5. Sonuc donmeli
        """
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "  Sonuc  "}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Adim 1-5
        result = translate("  Test metin  ")

        # Adim 1: Strip edilmis mi?
        call_data = mock_post.call_args[1]["json"]
        assert "  Test metin  " not in call_data["prompt"], (
            "Adim 1 FAIL: Strip yapilmamis"
        )

        # Adim 2: Prompt dogru mu?
        assert "Test metin" in call_data["prompt"], "Adim 2 FAIL: Metin prompt'ta yok"

        # Adim 3: API cagrildi mi?
        assert mock_post.called, "Adim 3 FAIL: API cagrilmadi"

        # Adim 5: Sonuc strip edilmis mi?
        assert result == "Sonuc", "Adim 5 FAIL: Sonuc strip edilmemis"


# ============================================================
# endregion
# ============================================================
