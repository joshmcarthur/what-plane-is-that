"""Tests for the TTL cache."""

from __future__ import annotations

import time

from what_plane.cache import TtlCache, cache_key
from what_plane.geo import bounding_box


def test_cache_key_is_stable_for_same_box() -> None:
    box = bounding_box(-41.29, 174.78, 15.0)
    assert cache_key(box) == cache_key(box)


def test_ttl_cache_expires_entries(monkeypatch) -> None:
    current = {"value": 0.0}

    def fake_time() -> float:
        return current["value"]

    monkeypatch.setattr(time, "time", fake_time)

    cache: TtlCache[str] = TtlCache(ttl_seconds=5.0)
    cache.set("key", "value")
    assert cache.get("key") == "value"

    current["value"] = 6.0
    assert cache.get("key") is None
