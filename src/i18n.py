import json
import logging
import os
import config

logger = logging.getLogger("i18n")

_translations = {}

def load_translations(lang: str = None):
    """Belirtilen dildeki JSON dosyasını yükler."""
    global _translations
    if lang is None:
        lang = getattr(config, "LANG", "tr")

    locale_path = os.path.join(os.path.dirname(__file__), "..", "locales", f"{lang}.json")
    
    try:
        if os.path.exists(locale_path):
            with open(locale_path, "r", encoding="utf-8") as f:
                _translations = json.load(f)
            logger.info(f"Lokalizasyon yüklendi: {lang}")
        else:
            logger.error(f"Lokalizasyon dosyası bulunamadı: {locale_path}")
            _translations = {}
    except Exception as e:
        logger.error(f"i18n yükleme hatası: {e}")
        _translations = {}

def _(key: str, default: str = None) -> str:
    """Metin anahtarını mevcut dile çevirir."""
    if not _translations:
        load_translations()
    
    val = _translations.get(key, default)
    if val is None:
        return key # Fallback: Anahtarın kendisi
    return val

# İlk yükleme
if not _translations:
    load_translations()
