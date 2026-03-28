"""
OCR-TRANSLATE — Metin Cache Modülü
Aynı altyazının tekrar tekrar çevrilmesini önlemek için benzerlik tabanlı cache.
Thread-safe, Boiling Frog korumalı.
"""

import threading
from collections import OrderedDict
from difflib import SequenceMatcher

from config import CACHE_MAX_SIZE, SIMILARITY_THRESHOLD


class TextCache:
    """Metin değişim tespiti ve çeviri cache'i."""

    def __init__(
        self,
        threshold: float = SIMILARITY_THRESHOLD,
        max_size: int = CACHE_MAX_SIZE,
    ) -> None:
        self._threshold = threshold
        self._max_size = max_size
        self._last_text: str = ""
        self._accumulated_diff: float = 0.0
        self._original_text: str = ""
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._lock = threading.Lock()

    def is_new_text(self, text: str) -> bool:
        """
        Verilen metin öncekiyle yeterince farklıysa True döner.
        Boş metin her zaman False döner (çeviri tetiklenmez).

        Boiling Frog Koruması: Küçük değişiklikler biriktirilir,
        toplam fark eşiği aşılırsa yeni metin kabul edilir.
        """
        cleaned = text.strip()
        if not cleaned:
            return False

        with self._lock:
            if not self._last_text:
                self._last_text = cleaned
                self._original_text = cleaned
                self._accumulated_diff = 0.0
                return True

            ratio = SequenceMatcher(None, self._last_text, cleaned).ratio()

            if ratio < self._threshold:
                # Kesin fark — kabul et
                self._last_text = cleaned
                self._original_text = cleaned
                self._accumulated_diff = 0.0
                return True

            # Küçük fark — biriktir
            diff = 1.0 - ratio
            self._accumulated_diff += diff
            self._last_text = cleaned

            # Boiling Frog eşiği: orijinal metinden toplam %30+ birikimli fark
            if self._accumulated_diff > 0.30:
                # Orijinal metne göre son bir karşılaştırma
                orig_ratio = SequenceMatcher(None, self._original_text, cleaned).ratio()
                if orig_ratio < self._threshold:
                    self._original_text = cleaned
                    self._accumulated_diff = 0.0
                    return True

            return False

    def get_cached_translation(self, text: str) -> str | None:
        """
        Cache'te bu metne benzer bir giriş varsa çevirisini döner.
        En yüksek benzerlik skorlu olanı bulur (ilk eşleşeni değil).
        """
        cleaned = text.strip()
        if not cleaned:
            return None

        with self._lock:
            # Önce tam eşleşme
            if cleaned in self._cache:
                self._cache.move_to_end(cleaned)
                return self._cache[cleaned]

            # En yüksek benzerlik skorlu olanı bul
            best_match = None
            best_ratio = 0.0

            for cached_text, translation in self._cache.items():
                ratio = SequenceMatcher(None, cached_text, cleaned).ratio()
                if ratio >= self._threshold and ratio > best_ratio:
                    best_ratio = ratio
                    best_match = translation

            if best_match:
                return best_match

            return None

    def store(self, source: str, translation: str) -> None:
        """Kaynak metin ve çevirisini cache'e ekler."""
        cleaned = source.strip()
        if not cleaned or not translation.strip():
            return

        with self._lock:
            self._cache[cleaned] = translation.strip()
            self._cache.move_to_end(cleaned)

            # Max boyutu aşarsa en eski girişi sil
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        """Cache'i temizler."""
        with self._lock:
            self._cache.clear()
            self._last_text = ""
            self._original_text = ""
            self._accumulated_diff = 0.0

    @property
    def size(self) -> int:
        """Cache'teki giriş sayısını döner."""
        with self._lock:
            return len(self._cache)
