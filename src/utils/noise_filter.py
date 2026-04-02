def is_translation_noise(text: str) -> bool:
    """Çeviri çıktısındaki gürültüyü tespit eder."""
    cleaned = text.strip()
    if not cleaned:
        return True
    if len(cleaned) < 2:
        return True
    # Teknik sızıntı kontrolü
    noise_patterns = [
        "Task:",
        "Guidelines:",
        "Return ONLY",
        "DO NOT",
        "Sen profesyonel",
        "Görev:",
        "Kurallar:",
        "Metin:",
        "Atmosfer:",
        "Format:",
        "Translation:",
    ]
    u = cleaned.upper()
    if any(p.upper() in u for p in noise_patterns):
        return True
    # Sembol ağırlıklı gürültü
    alpha_count = sum(1 for c in cleaned if c.isalpha() or c.isspace())
    if len(cleaned) > 0 and alpha_count / len(cleaned) < 0.4:
        return True
    return False
