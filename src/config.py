"""
OCR-TRANSLATE — Merkezi Konfigürasyon
Tüm uygulama ayarları bu dosyada tanımlanır.
"""

# region Ollama API Ayarları
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3:4b"
OLLAMA_TIMEOUT = 15  # saniye
# endregion

# region OCR Ayarları
OCR_LANG = "eng"
OCR_PSM = 6  # Tek blok metin modu (altyazılar için ideal)
# endregion

# region Ekran Yakalama Ayarları
CAPTURE_INTERVAL_MS = 750  # milisaniye (saniyede ~1.3 yakalama)
# endregion

# region Cache Ayarları
SIMILARITY_THRESHOLD = 0.85  # SequenceMatcher benzerlik eşiği
CACHE_MAX_SIZE = 20  # Maksimum cache girişi
# endregion

# region Temama ve Görsel Ayarlar (AAA Style)
THEME = {
    "bg_dark": "#0A0A0B",        # Derin siyah/lacivert
    "bg_card": "#161618",        # Kart arka planı
    "accent_blue": "#00A2FF",    # Elektrik mavisi
    "accent_cyan": "#00E5FF",    # Turkuaz/Cyan
    "accent_purple": "#7000FF",  # Mor aksan
    "text_primary": "#F2F2F2",   # Ana metin
    "text_secondary": "#A0A0A5", # İkincil metin
    "success": "#00E676",        # Başarı yeşili
    "error": "#FF5252",          # Hata kırmızısı
    "warning": "#FFD600",        # Uyarı sarısı
    "border": "#2A2A2D",         # Sınır çizgisi
    "shadow_color": "rgba(0, 0, 0, 0.6)",
    "glass_opacity": 0.8
}

OVERLAY_FONT_FAMILY = "Outfit, Sans"  # Outfit varsa öncelikli
OVERLAY_FONT_SIZE = 30
OVERLAY_FONT_COLOR = "#FFFFFF"
OVERLAY_OUTLINE_COLOR = "#000000"
OVERLAY_OUTLINE_WIDTH = 2
OVERLAY_BG_COLOR = "rgba(10, 10, 12, 190)"  # Daha koyu ve premium cam efekti
OVERLAY_PADDING = 16
OVERLAY_MARGIN_TOP = 8
# endregion

# region Çeviri Prompt'u
TRANSLATION_PROMPT = (
    "Translate the following English text to Turkish (Subtitle style). "
    "Return ONLY the Turkish translation, nothing else. "
    "Keep it natural and expressive.\n\n"
    "{text}"
)
# endregion

