#!/bin/bash
# OCR-TRANSLATE — Robust Launcher (Universal Style)

# Proje dizinine git
cd "$(dirname "$0")"

# Sanal ortam dizini
VENV_DIR="venv"

# 1. Sanal ortam yoksa oluştur
if [ ! -d "$VENV_DIR" ]; then
    echo "Sanal ortam (venv) bulunamadı! Kuruluyor..."
    python3 -m venv "$VENV_DIR"
fi

# 2. Sanal ortamı aktifleştir
source "$VENV_DIR/bin/activate"

# 3. Bağımlılıkları kontrol et ve kur (Sessiz mod)
echo "Bağımlılıklar kontrol ediliyor..."
pip install -r requirements.txt --quiet

# 4. Uygulamayı başlat
echo "OCR-TRANSLATE başlatılıyor..."
python src/main.py

# 5. Hata durumunda terminali açık tut (Diagnostic)
if [ $? -ne 0 ]; then
    echo "-----------------------------------"
    echo "Uygulama beklenmedik bir şekilde kapandı."
    echo "Lütfen yukarıdaki hata mesajlarını kontrol edin."
    echo "Çıkmak için ENTER tuşuna basın..."
    read -r
fi
