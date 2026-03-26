"""
OCR-TRANSLATE — Çeviri Modülü
Ollama API üzerinden yerel LLM ile İngilizce→Türkçe çeviri.
"""

import json
import logging

import requests

from config import OLLAMA_MODEL, OLLAMA_TIMEOUT, OLLAMA_URL, TRANSLATION_PROMPT

logger = logging.getLogger(__name__)


def translate(text: str, model: str = OLLAMA_MODEL) -> str | None:
    """
    Verilen İngilizce metni Ollama API ile Türkçe'ye çevirir.
    Başarısız olursa None döner.
    """
    cleaned = text.strip()
    if not cleaned:
        return None

    prompt = TRANSLATION_PROMPT.format(text=cleaned)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 256,
        },
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()

        data = response.json()
        result = data.get("response", "").strip()

        if result:
            logger.info("Çeviri başarılı: '%s' → '%s'", cleaned[:50], result[:50])
            return result

        logger.warning("Ollama boş yanıt döndü")
        return None

    except requests.exceptions.ConnectionError:
        logger.error("Ollama'ya bağlanılamadı. Servis çalışıyor mu? (%s)", OLLAMA_URL)
        return None
    except requests.exceptions.Timeout:
        logger.error("Ollama yanıt zaman aşımına uğradı (%ds)", OLLAMA_TIMEOUT)
        return None
    except (requests.exceptions.RequestException, json.JSONDecodeError) as exc:
        logger.error("Çeviri hatası: %s", exc)
        return None


def check_ollama_connection(model: str = OLLAMA_MODEL) -> bool:
    """Ollama servisinin çalışıp çalışmadığını kontrol eder."""
    try:
        # Ollama'nın sağlık kontrolü
        base_url = OLLAMA_URL.rsplit("/api", 1)[0]
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        response.raise_for_status()

        tags = response.json()
        available_models = [m["name"] for m in tags.get("models", [])]

        # Model adını normalize et (tag olmadan da eşleş)
        model_base = model.split(":")[0]
        model_found = any(
            m == model or m.startswith(f"{model_base}:") for m in available_models
        )

        if not model_found:
            logger.warning(
                "Model '%s' bulunamadı. Mevcut modeller: %s",
                model,
                ", ".join(available_models) if available_models else "yok",
            )
            return False

        logger.info("Ollama bağlantısı başarılı. Model '%s' hazır.", model)
        return True

    except requests.exceptions.RequestException as exc:
        logger.error("Ollama bağlantı kontrolü başarısız: %s", exc)
        return False


def test_model_response(model: str = OLLAMA_MODEL) -> tuple[bool, str]:
    """
    Modele kısa bir test mesajı gönderir ve gerçekten çalışıp çalışmadığını doğrular.
    Dönüş: (başarılı_mı, durum_mesajı)
    """
    test_prompt = "Translate to Turkish: Hello"
    payload = {
        "model": model,
        "prompt": test_prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 32,
        },
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()
        result = data.get("response", "").strip()

        if result:
            logger.info("Model testi başarılı: '%s' → '%s'", model, result[:50])
            return True, result[:80]

        logger.warning("Model test yanıtı boş: %s", model)
        return False, "Model boş yanıt döndü"

    except requests.exceptions.ConnectionError:
        return False, "Ollama servisine bağlanılamadı"
    except requests.exceptions.Timeout:
        return False, "Model yanıt zaman aşımına uğradı (30s)"
    except (requests.exceptions.RequestException, json.JSONDecodeError) as exc:
        return False, f"Model test hatası: {exc}"
