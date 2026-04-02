"""
OCR-TRANSLATE — Çeviri Modülü
Ollama API üzerinden yerel LLM ile İngilizce→Türkçe çeviri.
"""

import json
import logging
import requests
from config import OLLAMA_MODEL, OLLAMA_TIMEOUT, OLLAMA_URL, TRANSLATION_PROMPT, LANG
import time

logger = logging.getLogger(__name__)

try:
    from deep_translator import GoogleTranslator

    HAS_GOOGLE_TRANS = True
except Exception:
    GoogleTranslator = None
    HAS_GOOGLE_TRANS = False


# region TRANSLATOR REGISTRY
class BaseTranslator:
    def translate(self, text: str, **kwargs) -> str | None:
        raise NotImplementedError


class OllamaTranslator(BaseTranslator):
    def __init__(self, model: str = OLLAMA_MODEL):
        self.model = model

    def translate(self, text: str, **kwargs) -> str | None:
        cleaned = text.strip()
        if not cleaned:
            return None

        prompt = TRANSLATION_PROMPT.replace("{text}", cleaned)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 512},
        }
        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
            response.raise_for_status()
            result = response.json().get("response", "").strip()
            if result and not _is_prompt_leak(result):
                return result
        except Exception as e:
            logger.error(f"Ollama error: {e}")
        return None


class GoogleTranslatorBackend(BaseTranslator):
    def translate(self, text: str, **kwargs) -> str | None:
        if not HAS_GOOGLE_TRANS:
            return None
        try:
            return GoogleTranslator(source="en", target="tr").translate(text)
        except Exception as e:
            logger.error(f"Google error: {e}")
            return None


class TranslatorFactory:
    _instances = {}

    @classmethod
    def get_translator(cls, engine_type: str, model: str = OLLAMA_MODEL):
        key = f"{engine_type}_{model}"
        if key not in cls._instances:
            if engine_type == "google":
                cls._instances[key] = GoogleTranslatorBackend()
            else:
                cls._instances[key] = OllamaTranslator(model)
        return cls._instances[key]


# endregion


def translate(text: str, model: str = OLLAMA_MODEL, retries: int = 2) -> str | None:
    engine_type = "google" if model == "google" else "ollama"
    translator = TranslatorFactory.get_translator(engine_type, model)

    for attempt in range(retries + 1):
        result = translator.translate(text)
        if result:
            return result
        if attempt < retries:
            time.sleep(0.5)
    return None

    # Google Translate Mantığı
    if model == "google":
        if not HAS_GOOGLE_TRANS:
            logger.error("Google Translate (deep-translator) kütüphanesi yüklü değil!")
            return None
        try:
            # deep-translator kütüphanesi ile Google üzerinden çeviri
            result = GoogleTranslator(source="en", target="tr").translate(cleaned)
            if result:
                logger.info(
                    "Google Çeviri başarılı: '%s' -> '%s'", cleaned[:50], result[:50]
                )
                return result
            return None
        except Exception as e:
            logger.error("Google Çeviri hatası: %s", e)
            return None

    # Ollama LLM Mantığı (Mevcut kod)
    prompt = TRANSLATION_PROMPT.replace("{text}", cleaned)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 512,
            "repeat_penalty": 1.1,
            "top_p": 0.9,
        },
    }

    last_exc = None
    for attempt in range(retries + 1):
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
                # Prompt sızıntısı kontrolü
                if _is_prompt_leak(result):
                    logger.warning(
                        "Çeviri prompt sızıntısı tespit edildi, retry (%d/%d)",
                        attempt + 1,
                        retries,
                    )
                    continue
                logger.info("Çeviri başarılı: '%s' → '%s'", cleaned[:50], result[:50])
                return result

            logger.warning(
                "Ollama boş yanıt döndü (attempt %d/%d)", attempt + 1, retries
            )
            if attempt < retries:
                continue
            return None

        except requests.exceptions.ConnectionError as exc:
            last_exc = exc
            logger.error(
                "Ollama'ya bağlanılamadı (attempt %d/%d). Servis çalışıyor mu? (%s)",
                attempt + 1,
                retries,
                OLLAMA_URL,
            )
            if attempt < retries:
                continue
            break
        except requests.exceptions.Timeout as exc:
            last_exc = exc
            logger.error(
                "Ollama yanıt zaman aşımına uğradı (attempt %d/%d, %ds)",
                attempt + 1,
                retries,
                OLLAMA_TIMEOUT,
            )
            if attempt < retries:
                continue
        except (requests.exceptions.RequestException, json.JSONDecodeError) as exc:
            last_exc = exc
            logger.error("Çeviri hatası (attempt %d/%d): %s", attempt + 1, retries, exc)
            if attempt < retries:
                continue

    return None


def _is_prompt_leak(text: str) -> bool:
    """Modelin sistem promptunu döndürüp döndürmediğini kontrol eder."""
    leak_patterns = [
        "Atmosfer:",
        "Gürültüyü",
        "Diyalog akışı",
        "Seçici çeviri",
        "Teknik filtre",
        "Format:",
        "Kelime kelime",
        "duygusal ve dinamik",
        "Task:",
        "Guidelines:",
        "Return ONLY",
        "DO NOT",
        "Persona:",
        "Sen profesyonel bir",
        "Görev:",
        "Kurallar:",
    ]
    u = text.upper()
    return any(p.upper() in u for p in leak_patterns)


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
        # BUG FIX #4: Tam eşleşme kontrolü (startswith yerine split(':') kullanıldı)
        model_base = model.split(":")[0]
        model_found = any(
            m == model or m.split(":")[0] == model_base for m in available_models
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
