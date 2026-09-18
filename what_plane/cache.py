"""Simple TTL cache for upstream ADS-B Exchange responses."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass

from what_plane.adsbexchange import AdsbExchangeClient, FetchResult
from what_plane.geo import BoundingBox


@dataclass
class CacheEntry[T]:
    value: T
    expires_at: float


class TtlCache[T]:
    def __init__(self, ttl_seconds: float) -> None:
        self.ttl_seconds = ttl_seconds
        self._entries: dict[str, CacheEntry[T]] = {}

    def get(self, key: str) -> T | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= time.time():
            del self._entries[key]
            return None
        return entry.value

    def set(self, key: str, value: T) -> None:
        self._entries[key] = CacheEntry(
            value=value,
            expires_at=time.time() + self.ttl_seconds,
        )

    def clear(self) -> None:
        self._entries.clear()


def cache_key(box: BoundingBox) -> str:
    return f"{box.south:.2f}:{box.north:.2f}:{box.west:.2f}:{box.east:.2f}"


def cache_ttl_seconds() -> float:
    return float(os.getenv("CACHE_TTL_SECONDS", "8"))


class AdsbFetchCache:
    """TTL cache with single-flight fetch coalescing for ADS-B Exchange."""

    def __init__(self, ttl_seconds: float) -> None:
        self.ttl_seconds = ttl_seconds
        self._cache: TtlCache[FetchResult] = TtlCache(ttl_seconds)
        self._lock = asyncio.Lock()

    def clear(self) -> None:
        self._cache.clear()

    async def fetch(
        self,
        client: AdsbExchangeClient,
        box: BoundingBox,
    ) -> FetchResult:
        key = cache_key(box)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        async with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached

            result = await client.fetch_box(box)
            self._cache.set(key, result)
            return result
