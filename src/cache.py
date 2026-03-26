"""
OCR-TRANSLATE — Metin Cache Modülü
Aynı altyazının tekrar tekrar çevrilmesini önlemek için benzerlik tabanlı cache.
"""

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
        self._cache: OrderedDict[str, str] = OrderedDict()

    def is_new_text(self, text: str) -> bool:
        """
        Verilen metin öncekiyle yeterince farklıysa True döner.
        Boş metin her zaman False döner (çeviri tetiklenmez).
        """
        cleaned = text.strip()
        if not cleaned:
            return False

        if not self._last_text:
            self._last_text = cleaned
            return True

        ratio = SequenceMatcher(None, self._last_text, cleaned).ratio()
        if ratio < self._threshold:
            self._last_text = cleaned
            return True

        return False

    def get_cached_translation(self, text: str) -> str | None:
        """
        Cache'te bu metne benzer bir giriş varsa çevirisini döner.
        Tam eşleşme veya yüksek benzerlik arar.
        """
        cleaned = text.strip()
        if not cleaned:
            return None

        # Önce tam eşleşme
        if cleaned in self._cache:
            self._cache.move_to_end(cleaned)
            return self._cache[cleaned]

        # Benzerlik araması
        for cached_text, translation in self._cache.items():
            ratio = SequenceMatcher(None, cached_text, cleaned).ratio()
            if ratio >= self._threshold:
                return translation

        return None

    def store(self, source: str, translation: str) -> None:
        """Kaynak metin ve çevirisini cache'e ekler."""
        cleaned = source.strip()
        if not cleaned or not translation.strip():
            return

        self._cache[cleaned] = translation.strip()
        self._cache.move_to_end(cleaned)

        # Max boyutu aşarsa en eski girişi sil
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        """Cache'i temizler."""
        self._cache.clear()
        self._last_text = ""
