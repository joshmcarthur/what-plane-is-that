"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from what_plane import aircraft_db
from what_plane.bincraft import Aircraft


@pytest.fixture(autouse=True)
def disable_aircraft_db_by_default(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("AIRCRAFT_DB_ENABLED", "false")
    monkeypatch.delenv("AIRCRAFT_DB_PATH", raising=False)
    monkeypatch.delenv("AIRCRAFT_DB_PREFIXES", raising=False)
    aircraft_db.reset_aircraft_db_state()
    yield
    aircraft_db.reset_aircraft_db_state()


@pytest.fixture(autouse=True)
def observer_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("OBSERVER_LAT", "-41.29")
    monkeypatch.setenv("OBSERVER_LNG", "174.78")
    monkeypatch.setenv("NEAREST_RADIUS_KM", "15")
    monkeypatch.setenv("NEAREST_MAX_ALT_FT", "15000")
    monkeypatch.setenv("NEAREST_MAX_SEEN_POS_S", "20")
    monkeypatch.setenv("ADSBDB_ENABLED", "false")
    yield


@pytest.fixture
def sample_aircraft() -> Aircraft:
    return Aircraft(
        hex="abc123",
        flight="TEST1",
        registration="ZK-TEST",
        type_code="C172",
        lat=-41.30,
        lon=174.77,
        alt_baro_ft=1200,
        ground_speed_kts=90.0,
        track_deg=180.0,
        squawk="1200",
        seen_pos_s=5.0,
        seen_s=5.0,
        rssi_db=-10.0,
        addr_type="adsb_icao",
        category=None,
        on_ground=False,
    )
