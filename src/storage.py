import json
import os
import logging
import tempfile
from typing import Dict, Any

logger = logging.getLogger(__name__)

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")

DEFAULT_SETTINGS = {
    "model": "gemma3:4b",
    "interval": 1000,  # Performans için artırıldı
    "ocr_engine_type": "tesseract",  # İngilizce çizgi roman için en hızlı
    "overlay_mode": "inplace",
    "vision_model": "glm-ocr",
    "capture_method": "auto",
    "enable_refiner": False,  # Performans için devre dışı
    "show_source_text": True,
}


def load_settings() -> Dict[str, Any]:
    """Ayarları dosyadan yükler."""
    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS.copy()

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ayarlar yüklenemedi: {e}")
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: Dict[str, Any]):
    """Ayarları dosyaya kaydeder (atomic write)."""
    try:
        current = load_settings()
        current.update(settings)

        # Atomic write: önce geçici dosyaya yaz, sonra rename et
        dir_name = os.path.dirname(SETTINGS_FILE)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=4, ensure_ascii=False)
            os.replace(tmp_path, SETTINGS_FILE)
        except Exception:
            # Hata durumunda geçici dosyayı temizle
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except Exception as e:
        logger.error(f"Ayarlar kaydedilemedi: {e}")


def update_setting(key: str, value: Any):
    """Tek bir ayarı günceller."""
    settings = load_settings()
    settings[key] = value
    save_settings(settings)
