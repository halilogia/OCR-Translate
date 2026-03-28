"""
OCR-TRANSLATE — Merkezi Konfigürasyon
Tüm uygulama ayarları bu dosyada tanımlanır.
"""

LANG = "tr"  # "tr" veya "en" (Sovereign i18n)
CAPTURE_METHOD = "auto"  # "auto", "aura", "kde" (Sovereign Capture)

# region Ollama API Ayarları
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3:4b"
OLLAMA_TIMEOUT = 30  # saniye (Ağır modeller için artırıldı)
# endregion

# region OCR Ayarları
OCR_ENGINE_TYPE = "easyocr"  # "easyocr", "tesseract" veya "vision"
VISION_MODEL = "glm-ocr"  # Ollama vision modelleri (Llama 3.2-Vision vb.)
REFINER_MODEL = "gemma:2b"  # Hızlı ve hafif model tercih dildi
ENABLE_REFINER = True  # Varsayılan olarak aktif
OCR_LANG = "eng"
OCR_PSM = 6  # Tek blok metin modu (altyazılar için ideal)
# endregion

# region Overlay Tasarımı (AAA Standards)
OVERLAY_MODE = "inplace"  # "bottom" (Altta) veya "inplace" (Metin üzerine)

# region Ekran Yakalama Ayarları
CAPTURE_INTERVAL_MS = 750  # milisaniye (saniyede ~1.3 yakalama)
CONSOLE_LOG_FILE = "console.log"  # AAA Debugging
# endregion

# region Cache Ayarları
SIMILARITY_THRESHOLD = 0.85  # SequenceMatcher benzerlik eşiği
CACHE_MAX_SIZE = 20  # Maksimum cache girişi
# endregion

# region Temama ve Görsel Ayarlar (AAA Style)
THEME = {
    "bg_dark": "#0A0A0B",  # Derin siyah/lacivert
    "bg_card": "#161618",  # Kart arka planı
    "accent_blue": "#00A2FF",  # Elektrik mavisi
    "accent_cyan": "#00E5FF",  # Turkuaz/Cyan
    "accent_purple": "#7000FF",  # Mor aksan
    "text_primary": "#F2F2F2",  # Ana metin
    "text_secondary": "#A0A0A5",  # İkincil metin
    "success": "#00E676",  # Başarı yeşili
    "error": "#FF5252",  # Hata kırmızısı
    "warning": "#FFD600",  # Uyarı sarısı
    "border": "#2A2A2D",  # Sınır çizgisi
    "shadow_color": "rgba(0, 0, 0, 0.6)",
    "glass_opacity": 0.8,
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

# region Çeviri Prompt'u (AAA Cinematic & Manga-Specific)
TRANSLATION_PROMPT = (
    "Sen profesyonel bir manga, manhwa, oyun ve görsel roman çevirmenisin. "
    "Amacın doğal, akıcı ve atmosfere uygun Türkçe çeviri üretmektir.\n\n"
    "Görev: Aşağıdaki İngilizce OCR metnini Türkçe'ye çevir.\n\n"
    "Kurallar:\n"
    "1. ATMOSFER: Manga/oyun tonuna uygun sinematik ve doğal Türkçe kullan. "
    "Kelime kelime çeviri yapma. Örn: 'You shouldn't do this!' → 'Sakın yapma!' veya 'Yapmamalıydın!'\n"
    "2. GÜRÜLTÜ TEMİZLİĞİ: |, [, ], {{, }}, _, =, > gibi teknik sembolleri kaldır. "
    "Bunlar OCR hatalarıdır.\n"
    "3. DİYALOG: Karakter konuşması gibi hissettiriyorsa duygusal ve dinamik ifadeler kullan.\n"
    "4. SEÇİMLİ ÇEVİRİ: Kişi isimleri, yer isimleri veya zaten Türkçe olan kelimeleri değiştirme.\n"
    "5. TEKNİK FİLTRE: 'model', 'interval', 'vision', 'config' gibi teknik kelimeler görüyorsan boş string döndür. "
    "Bunlar arayüz gürültüsüdür.\n"
    "6. FORMAT: Sadece çevrilmiş metni döndür. 'Çeviri:', 'Translation:' veya açıklama ekleme.\n"
    "7. KALİTE: Anlamı koru, akıcılık sağla. Kısa ve vurucu ifadeler tercih et.\n\n"
    "Metin:\n{text}"
)
# endregion
