#!/bin/bash
# OCR-TRANSLATE Launcher Script

# Proje dizinine git
cd "$(dirname "$0")"

# (Opsiyonel) Güncellemeleri al (GitHub'dan otomatik çekmek istersen alttaki satırı aktiflesebilirsin)
# git pull origin main

# Sanal ortamı kontrol et ve aktifleştir
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Sanal ortam (venv) bulunamadı! Lütfen önce kurulumu yapın."
    exit 1
fi

# Uygulamayı başlat
python src/main.py
