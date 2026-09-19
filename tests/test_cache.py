"""Tests for the TTL cache."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from what_plane.adsbexchange import AdsbExchangeClient, FetchResult
from what_plane.cache import AdsbFetchCache, TtlCache, cache_key
from what_plane.geo import BoundingBox, bounding_box


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


@pytest.mark.asyncio
async def test_adsb_fetch_cache_coalesces_concurrent_fetches() -> None:
    box = bounding_box(-41.29, 174.78, 15.0)
    fetch_result = FetchResult(
        aircraft=[],
        fetched_at=1_700_000_000.0,
        source_url="https://example.test/",
    )
    client = AdsbExchangeClient()
    call_count = 0

    async def slow_fetch(box: BoundingBox) -> FetchResult:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return fetch_result

    client.fetch_box = slow_fetch  # type: ignore[method-assign]
    cache = AdsbFetchCache(ttl_seconds=60.0)

    first, second = await asyncio.gather(
        cache.fetch(client, box),
        cache.fetch(client, box),
    )

    assert first == second
    assert call_count == 1


@pytest.mark.asyncio
async def test_adsb_fetch_cache_returns_cached_value_inside_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    box = bounding_box(-41.29, 174.78, 15.0)
    fetch_result = FetchResult(
        aircraft=[],
        fetched_at=1_700_000_000.0,
        source_url="https://example.test/",
    )
    client = AdsbExchangeClient()
    fetch_box = AsyncMock(return_value=fetch_result)
    client.fetch_box = fetch_box
    cache = AdsbFetchCache(ttl_seconds=60.0)
    cache._cache.set(cache_key(box), fetch_result)

    result = await cache.fetch(client, box)

    assert result == fetch_result
    fetch_box.assert_not_awaited()
