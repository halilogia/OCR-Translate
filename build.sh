#!/usr/bin/env bash
# ============================================================
# OCR-TRANSLATE — Linux Build Script
# Tek dosya çalıştırılabilir (portable binary) oluşturur.
#
# Kullanım:
#   chmod +x build.sh
#   ./build.sh
#
# Çıktı:
#   dist/ocr-translate  (tek dosya, ~80-120 MB)
#
# Gereksinimler:
#   - Python 3.10+
#   - pip install pyinstaller
#   - Sistem: tesseract, tesseract-data-eng
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  OCR-TRANSLATE Build"
echo "========================================"

# Sanal ortamı etkinleştir (varsa)
if [ -d "venv" ]; then
    echo "[1/4] Sanal ortam etkinleştiriliyor..."
    source venv/bin/activate
else
    echo "[1/4] Sanal ortam bulunamadı, sistem Python kullanılıyor..."
fi

# PyInstaller kontrolü
if ! command -v pyinstaller &> /dev/null; then
    echo "[!] PyInstaller bulunamadı. Kuruluyor..."
    pip install pyinstaller --quiet
fi

# Eski build dosyalarını temizle
echo "[2/4] Eski build dosyaları temizleniyor..."
rm -rf build/ dist/

# Build
echo "[3/4] Build başlıyor..."
pyinstaller \
    --onefile \
    --noconsole \
    --strip \
    --name ocr-translate \
    --paths src \
    --hidden-import PyQt5 \
    --hidden-import PyQt5.QtCore \
    --hidden-import PyQt5.QtGui \
    --hidden-import PyQt5.QtWidgets \
    --hidden-import pytesseract \
    --hidden-import cv2 \
    --hidden-import mss \
    --hidden-import mss.linux \
    --hidden-import numpy \
    --hidden-import PIL \
    --hidden-import requests \
    --exclude-module tkinter \
    --exclude-module matplotlib \
    --exclude-module scipy \
    --exclude-module pandas \
    src/main.py

# Çalıştırma izni ver
chmod +x dist/ocr-translate

# Sonuç
echo ""
echo "========================================"
echo "  Build Tamamlandı!"
echo "========================================"
echo ""
echo "  Dosya: dist/ocr-translate"
echo "  Boyut: $(du -h dist/ocr-translate | cut -f1)"
echo ""
echo "  Çalıştırma:"
echo "    ./dist/ocr-translate"
echo "    ./dist/ocr-translate --model gemma3:4b"
echo "    ./dist/ocr-translate --fullscreen"
echo ""
echo "  Sistem Gereksinimleri:"
echo "    - tesseract + tesseract-data-eng"
echo "    - ollama (çeviri için)"
echo "========================================"
