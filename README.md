# 🔤 OCR-TRANSLATE

Linux masaüstünde çalışan, ekrandaki İngilizce metni gerçek zamanlı olarak Türkçe'ye çevirip şeffaf overlay ile gösteren uygulama.

## ✨ Özellikler

- **Alan Seçimi**: Fare ile istediğiniz dikdörtgen alanı seçin veya tam ekran modunda kullanın
- **Gerçek Zamanlı OCR**: Tesseract ile saniyede ~1.3 ekran taraması
- **Yerel Çeviri**: Ollama API ile tamamen çevrimdışı İngilizce→Türkçe çeviri
- **Şeffaf Overlay**: Tıklanamaz (click-through), oyunun/tarayıcının üzerinde görünür
- **Akıllı Cache**: Aynı metin tekrar çevrilmez, sistem gereksiz yüklenmez
- **System Tray**: Durdur/Devam Et/Bölge Değiştir/Çık

## 📋 Gereksinimler

### Sistem Paketleri (Arch/CachyOS)

```bash
sudo pacman -S tesseract tesseract-data-eng python-pip
```

### Ollama

```bash
# Ollama kurulumu (eğer kurulu değilse)
curl -fsSL https://ollama.com/install.sh | sh

# Servisi başlat
ollama serve

# Modeli indir (başka terminalde)
ollama pull gemma3:4b
```

### Python Bağımlılıkları (Sanal Ortam Önerilir)

Arch Linux'ta sistem paketlerini korumak için sanal ortam kullanmanız önerilir:

```bash
cd OCR-TRANSLATE
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> **Not**: `opencv-python` Tesseract ön işleme için gereklidir. Arch'ta `python-opencv` paketi tercih edilebilir:
> ```bash
> sudo pacman -S python-opencv
> ```

## 🚀 Kullanım

### Temel Kullanım

```bash
python src/main.py
```

1. **Dashboard**: Uygulama açıldığında modern bir kontrol paneli görünür.
2. **Bağlantı**: Ollama servis durumu otomatik kontrol edilir.
3. **Alan Seçimi**: "Bölge Seç" butonuna tıklayın, ekran kararır. Fare ile çevrilecek alanı seçin (altyazı bölgesi).
4. **Çeviri**: "Başlat" butonuna tıklayın. Overlay otomatik olarak çeviri göstermeye başlar.
5. **Kontrol**: Dashboard üzerinden veya System tray ikonundan (sağ tıklayarak) yönetebilirsiniz.

### Kısayollar (Alan Seçimi Ekranında)

| Tuş | İşlev |
|-----|-------|
| **Fare sürükle** | Dikdörtgen alan seç |
| **F** | Tam ekran seç |
| **ESC** | İptal |

### CLI Argümanları

```bash
# Farklı model kullan
python src/main.py --model llama3

# Yakalama aralığını değiştir (ms)
python src/main.py --interval 1000

# Tam ekran modunda başlat
python src/main.py --fullscreen

# Hepsini birleştir
python src/main.py --model gemma3:4b --interval 500 --fullscreen
```

## 📁 Proje Yapısı

```
OCR-TRANSLATE/
├── src/
│   ├── main.py             # Ana uygulama (orkestrasyon)
│   ├── config.py           # Merkezi ayarlar
│   ├── screen_capture.py   # mss ile ekran yakalama
│   ├── region_selector.py  # Fare ile alan seçimi
│   ├── ocr_engine.py       # Tesseract OCR
│   ├── translator.py       # Ollama API istemcisi
│   ├── cache.py            # Metin cache sistemi
│   └── overlay.py          # Şeffaf overlay penceresi
├── requirements.txt
└── README.md
```

## ⚙️ Yapılandırma

`src/config.py` dosyasından tüm ayarları değiştirebilirsiniz:

- **OLLAMA_MODEL**: Çeviri modeli
- **CAPTURE_INTERVAL_MS**: Ekran yakalama sıklığı
- **SIMILARITY_THRESHOLD**: Cache benzerlik eşiği
- **OVERLAY_FONT_SIZE**: Çeviri metin boyutu
- **OVERLAY_FONT_COLOR**: Metin rengi

## 🐛 Sorun Giderme

| Sorun | Çözüm |
|-------|-------|
| "Ollama bağlantısı kurulamadı" | `ollama serve` çalıştırın |
| "Model bulunamadı" | `ollama pull gemma3:4b` çalıştırın |
| OCR metin okumuyor | Altyazı bölgesini daha dar seçin |
| Overlay görünmüyor | X11 oturumu kullanın (Wayland'da sınırlı destek) |
| Çeviri çok yavaş | Daha küçük model deneyin: `--model gemma3:1b` |
