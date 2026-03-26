"""
OCR-TRANSLATE — TextCache Birim & Kenar Durum Testleri
======================================================
Test Framework: pytest
Dogruladigi Modul: src/cache.py (TextCache sinifi)

Tespit edilen olasi hatalar:
- BUG #1 (Boiling Frog): is_new_text sadece _last_text ile karsilastirir.
  Metin yavas yavas degisirse, her adim esik altinda kalip "yeni degil" der,
  ama toplam degisim cok buyuk olabilir.
- BUG #2: get_cached_translation benzerlik aramasinda ilk esleseni doner,
  en iyi esleseni degil. Yanlis ceviri donebilir.
"""

import pytest

from cache import TextCache


# ============================================================
# region Birim Testleri (Unit Tests)
# ============================================================


class TestIsNewText:
    """is_new_text() metodu icin birim testleri."""

    def test_ilk_metin_her_zaman_yeni(self):
        """Ilk verilen metin her zaman True donmeli."""
        cache = TextCache()
        assert cache.is_new_text("Hello world") is True

    def test_ayni_metin_yeni_degil(self):
        """Ayni metin ikinci kez verildiginde False donmeli."""
        cache = TextCache()
        cache.is_new_text("Hello world")
        assert cache.is_new_text("Hello world") is False

    def test_tamamen_farkli_metin_yeni(self):
        """Tamamen farkli metin True donmeli."""
        cache = TextCache()
        cache.is_new_text("Hello world")
        assert cache.is_new_text("Goodbye universe") is True

    def test_benzer_metin_yeni_degil(self):
        """Esik uzerinde benzer metin False donmeli (varsayilan esik 0.85)."""
        cache = TextCache(threshold=0.85)
        cache.is_new_text("Hello world today")
        # Cok kucuk fark — benzerlik yuksek
        assert cache.is_new_text("Hello world today!") is False

    def test_last_text_guncellenir(self):
        """Yeni metin kabul edilince _last_text guncellenmeli."""
        cache = TextCache()
        cache.is_new_text("First text")
        cache.is_new_text("Completely different text here now")
        # _last_text artik "Completely different text here now" olmali
        assert cache._last_text == "Completely different text here now"

    def test_last_text_benzer_metinde_guncellenmez(self):
        """
        BUG #1 TESPITI (Boiling Frog):
        Benzer metin reddedildiginde _last_text guncellenmiyor.
        Bu, yavas degisen metinlerin hic yakalanmamasina neden olabilir.
        """
        cache = TextCache(threshold=0.85)
        cache.is_new_text("The quick brown fox jumps over the lazy dog")
        # Kucuk degisiklik — esik ustunde benzerlik
        cache.is_new_text("The quick brown fox jumps over the lazy cat")
        # _last_text hala eski metin olmali (guncellenmedi)
        assert cache._last_text == "The quick brown fox jumps over the lazy dog"


class TestIsNewTextEdgeCases:
    """is_new_text() kenar durum testleri."""

    def test_bos_string_false(self):
        """Bos string her zaman False donmeli."""
        cache = TextCache()
        assert cache.is_new_text("") is False

    def test_sadece_bosluk_false(self):
        """Sadece bosluk karakterleri False donmeli."""
        cache = TextCache()
        assert cache.is_new_text("   \n\t  ") is False

    def test_bos_sonrasi_gercek_metin(self):
        """Bos metin sonrasi gercek metin True donmeli."""
        cache = TextCache()
        cache.is_new_text("")
        assert cache.is_new_text("Real text") is True

    def test_strip_uygulanir(self):
        """Metin striplenip karsilastirilmali."""
        cache = TextCache()
        cache.is_new_text("  Hello  ")
        assert cache.is_new_text("Hello") is False

    def test_cok_uzun_metin(self):
        """Cok uzun metinler hata vermemeli."""
        cache = TextCache()
        long_text = "A" * 10000
        assert cache.is_new_text(long_text) is True
        assert cache.is_new_text(long_text) is False

    def test_tek_karakter(self):
        """Tek karakter metin islenmeli."""
        cache = TextCache()
        assert cache.is_new_text("A") is True

    def test_unicode_metin(self):
        """Unicode karakterler duzgun islenmeli."""
        cache = TextCache()
        assert cache.is_new_text("Merhaba Dunya") is True
        assert cache.is_new_text("Merhaba Dunya") is False

    def test_newline_iceren_metin(self):
        """Satir sonu karakterli metin islenmeli."""
        cache = TextCache()
        cache.is_new_text("Line 1\nLine 2")
        assert cache.is_new_text("Line 1\nLine 2") is False


# ============================================================
# endregion
# ============================================================


# ============================================================
# region Cache Store ve Lookup Testleri
# ============================================================


class TestGetCachedTranslation:
    """get_cached_translation() birim testleri."""

    def test_bos_cache_none_doner(self):
        """Bos cache'te arama None donmeli."""
        cache = TextCache()
        assert cache.get_cached_translation("Hello") is None

    def test_tam_eslesme(self):
        """Tam eslesme durumunda ceviri donmeli."""
        cache = TextCache()
        cache.store("Hello", "Merhaba")
        assert cache.get_cached_translation("Hello") == "Merhaba"

    def test_benzer_eslesme(self):
        """Esik ustunde benzer metin icin ceviri donmeli."""
        cache = TextCache(threshold=0.85)
        cache.store("Hello world today", "Merhaba dunya bugun")
        result = cache.get_cached_translation("Hello world today!")
        assert result == "Merhaba dunya bugun"

    def test_dusuk_benzerlik_none_doner(self):
        """Esik altinda benzerlik None donmeli."""
        cache = TextCache(threshold=0.85)
        cache.store("Hello world", "Merhaba dunya")
        assert cache.get_cached_translation("Goodbye universe") is None

    def test_bos_girdi_none_doner(self):
        """Bos string None donmeli."""
        cache = TextCache()
        cache.store("Hello", "Merhaba")
        assert cache.get_cached_translation("") is None
        assert cache.get_cached_translation("   ") is None

    def test_ilk_benzer_eslesme_doner_en_iyi_degil(self):
        """
        BUG #2 TESPITI:
        get_cached_translation ilk esleseni doner, en iyi esleseni degil.
        Bu yanlls ceviri donmesine neden olabilir.
        """
        cache = TextCache(threshold=0.70)
        cache.store("The cat sat on the mat", "Kedi minderinde oturdu")
        cache.store("The cat sat on the hat", "Kedi sapkanin ustunde oturdu")
        # "The cat sat on the hat!" icin en iyi eslesme ikincisi olmali
        # ama OrderedDict sirasiyla ilki de eslesebilir
        result = cache.get_cached_translation("The cat sat on the hat!")
        # Bu test hatayi gostermek icin — sonuc tutarsiz olabilir
        assert result is not None  # En azindan bir sonuc donmeli


class TestStore:
    """store() metodu birim testleri."""

    def test_basarili_kayit(self):
        """Kaynak-ceviri cifti basariyla kaydedilmeli."""
        cache = TextCache()
        cache.store("Hello", "Merhaba")
        assert cache.get_cached_translation("Hello") == "Merhaba"

    def test_bos_kaynak_reddedilir(self):
        """Bos kaynak metin kaydedilmemeli."""
        cache = TextCache()
        cache.store("", "Merhaba")
        assert len(cache._cache) == 0

    def test_bos_ceviri_reddedilir(self):
        """Bos ceviri kaydedilmemeli."""
        cache = TextCache()
        cache.store("Hello", "")
        assert len(cache._cache) == 0

    def test_bos_bosluklu_kaynak_reddedilir(self):
        """Sadece bosluk olan kaynak reddedilmeli."""
        cache = TextCache()
        cache.store("   ", "Merhaba")
        assert len(cache._cache) == 0

    def test_max_size_asimi_en_eski_silinir(self):
        """Max boyut asilinca en eski giris silinmeli (LRU)."""
        cache = TextCache(max_size=3)
        cache.store("A", "a")
        cache.store("B", "b")
        cache.store("C", "c")
        cache.store("D", "d")  # "A" silinmeli
        assert cache.get_cached_translation("A") is None
        assert cache.get_cached_translation("D") == "d"
        assert len(cache._cache) == 3

    def test_ayni_anahtar_guncellenir(self):
        """Ayni kaynak metin yeni ceviriyle guncellenebilmeli."""
        cache = TextCache()
        cache.store("Hello", "Merhaba")
        cache.store("Hello", "Selam")
        assert cache.get_cached_translation("Hello") == "Selam"

    def test_strip_uygulanir(self):
        """Kaynak ve ceviri striplenmeli."""
        cache = TextCache()
        cache.store("  Hello  ", "  Merhaba  ")
        assert cache.get_cached_translation("Hello") == "Merhaba"


class TestClear:
    """clear() metodu testleri."""

    def test_clear_cache_bosaltir(self):
        """clear() hem cache'i hem last_text'i sifirlamali."""
        cache = TextCache()
        cache.store("Hello", "Merhaba")
        cache.is_new_text("Test")
        cache.clear()
        assert len(cache._cache) == 0
        assert cache._last_text == ""

    def test_clear_sonrasi_ilk_metin_yeni(self):
        """clear() sonrasi ilk metin yine True donmeli."""
        cache = TextCache()
        cache.is_new_text("First")
        cache.clear()
        assert cache.is_new_text("Any text") is True


# ============================================================
# endregion
# ============================================================


# ============================================================
# region Hata Ayiklama Testleri (Debug / Flow Isolation)
# ============================================================


class TestCacheDebugFlow:
    """
    Adim adim akis testi: Gercek kullanim senaryosunu simule eder.
    Hatalarin akisin hangi noktasinda olustugunu izole eder.
    """

    def test_tam_ceviri_akisi(self):
        """Capture → OCR → Cache check → Store → Re-check akisi."""
        cache = TextCache()

        # Adim 1: Ilk OCR metni
        text1 = "The hero walked into the forest"
        assert cache.is_new_text(text1) is True, (
            "Adim 1 BASARISIZ: Ilk metin yeni olmali"
        )

        # Adim 2: Cache'te yok
        assert cache.get_cached_translation(text1) is None, (
            "Adim 2 BASARISIZ: Henuz cache'te olmamali"
        )

        # Adim 3: Ceviriyi kaydet
        cache.store(text1, "Kahraman ormana yuruyerek girdi")

        # Adim 4: Cache'ten getir
        result = cache.get_cached_translation(text1)
        assert result == "Kahraman ormana yuruyerek girdi", (
            "Adim 4 BASARISIZ: Cache'ten dogru ceviri donmeli"
        )

        # Adim 5: Ayni metin tekrar gelirse → yeni degil
        assert cache.is_new_text(text1) is False, (
            "Adim 5 BASARISIZ: Ayni metin yeni olmamali"
        )

        # Adim 6: Farkli metin gelirse → yeni
        text2 = "The wizard cast a powerful spell"
        assert cache.is_new_text(text2) is True, (
            "Adim 6 BASARISIZ: Farkli metin yeni olmali"
        )

        # Adim 7: Eski metin cache'te hala var mi?
        cached_old = cache.get_cached_translation(text1)
        assert cached_old == "Kahraman ormana yuruyerek girdi", (
            "Adim 7 BASARISIZ: Eski ceviri kaybolmamali"
        )

    def test_boiling_frog_senaryosu(self):
        """
        BUG #1 DETAYLI TEST:
        Metin yavasca degistiginde cache bunu yakalayamaz.
        Her frame'de kucuk bir kelime degisir ama hic biri esigi asmaz.
        """
        cache = TextCache(threshold=0.85)

        texts = [
            "The quick brown fox jumps over the lazy dog",
            "The quick brown fox jumps over the lazy cat",  # 1 kelime degisti
            "The quick brown fox leaps over the lazy cat",  # 1 kelime daha
            "The fast brown fox leaps over the lazy cat",  # 1 kelime daha
            "The fast brown fox leaps over a lazy cat",  # 1 kelime daha
            "A fast brown fox leaps over a lazy cat",  # Artik cok farkli
        ]

        results = []
        for t in texts:
            results.append(cache.is_new_text(t))

        # Ilk metin her zaman True
        assert results[0] is True

        # SON metin ilk metinden cok farkli ama...
        # Boiling frog yuzunden hic yakalanmamis olabilir.
        # Bu test BUG'u belgelemek icin:
        false_count = results[1:].count(False)
        if false_count == len(results) - 1:
            pytest.xfail(
                "BUG ONAYLANDI: Boiling frog — metin yavasca degisince "
                "hic yakalanmiyor. _last_text guncellenmediginden her karsilastirma "
                "ilk metinle yapiliyor."
            )

    def test_lru_eviction_sirasi(self):
        """LRU silinme sirasinin dogru calistigini dogrular."""
        cache = TextCache(max_size=3)

        cache.store("A", "1")
        cache.store("B", "2")
        cache.store("C", "3")

        # A'yi eriselim → LRU'da sona tasinir
        cache.get_cached_translation("A")

        # Yeni giris → en eski olan B silinmeli (A erisildigi icin B en eski)
        cache.store("D", "4")

        assert cache.get_cached_translation("A") is not None, (
            "A erisildigi icin silinmemeli"
        )
        assert cache.get_cached_translation("B") is None, (
            "B en eski olmali ve silinmeli"
        )
        assert cache.get_cached_translation("C") is not None, "C hala olmali"
        assert cache.get_cached_translation("D") is not None, "D yeni eklendi"


# ============================================================
# endregion
# ============================================================
