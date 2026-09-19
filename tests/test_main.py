"""Tests for the HTTP API."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import what_plane.main as main_module
from fastapi.testclient import TestClient
from what_plane.adsbexchange import FetchResult
from what_plane.bincraft import Aircraft
from what_plane.config import ObserverConfig


@pytest.fixture(autouse=True)
def reset_app_state() -> None:
    main_module.fetch_cache.clear()
    main_module.last_fetch = None
    main_module.observer_config = ObserverConfig(
        lat=-41.29,
        lng=174.78,
        radius_km=15.0,
        max_alt_ft=15_000,
        max_seen_pos_s=20.0,
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(main_module.app)


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["source"] == "adsbexchange"
    assert body["observer"]["lat"] == -41.29


def test_nearest_found(
    client: TestClient,
    sample_aircraft: Aircraft,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetch_result = FetchResult(
        aircraft=[sample_aircraft],
        fetched_at=1_700_000_000.0,
        source_url="https://example.test/",
    )
    monkeypatch.setattr(
        main_module.client,
        "fetch_box",
        AsyncMock(return_value=fetch_result),
    )

    response = client.get("/nearest")

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert body["flight"] == "TEST1"
    assert body["summary"]


def test_nearest_not_found(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetch_result = FetchResult(
        aircraft=[],
        fetched_at=1_700_000_000.0,
        source_url="https://example.test/",
    )
    monkeypatch.setattr(
        main_module.client,
        "fetch_box",
        AsyncMock(return_value=fetch_result),
    )

    response = client.get("/nearest")

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is False
    assert "don't see any aircraft" in body["summary"]


def test_nearest_upstream_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main_module.client,
        "fetch_box",
        AsyncMock(side_effect=RuntimeError("upstream unavailable")),
    )

    response = client.get("/nearest")

    assert response.status_code == 502


def test_nearest_reuses_cache_within_ttl(
    client: TestClient,
    sample_aircraft: Aircraft,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetch_result = FetchResult(
        aircraft=[sample_aircraft],
        fetched_at=1_700_000_000.0,
        source_url="https://example.test/",
    )
    fetch_box = AsyncMock(return_value=fetch_result)
    monkeypatch.setattr(main_module.client, "fetch_box", fetch_box)

    assert client.get("/nearest").status_code == 200
    assert client.get("/nearest").status_code == 200

    fetch_box.assert_awaited_once()


def test_nearest_requires_observer_config(client: TestClient) -> None:
    main_module.observer_config = None

    response = client.get("/nearest")

    assert response.status_code == 503


def test_lifespan_loads_observer_config_from_env() -> None:
    main_module.observer_config = None

    with TestClient(main_module.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["observer"]["lat"] == -41.29
    assert body["observer"]["lng"] == 174.78
    assert main_module.observer_config is not None
