"""Tests for nearest-aircraft selection."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest
from what_plane.bincraft import Aircraft
from what_plane.nearest import (
    NearestQuery,
    build_summary,
    describe_aircraft,
    find_nearest,
)


def _aircraft(
    *,
    hex: str,
    lat: float,
    lon: float,
    alt_baro_ft: int | None = 1200,
    seen_pos_s: float = 5.0,
    on_ground: bool = False,
    flight: str = "",
    registration: str = "",
    type_code: str = "C172",
) -> Aircraft:
    return Aircraft(
        hex=hex,
        flight=flight,
        registration=registration,
        type_code=type_code,
        lat=lat,
        lon=lon,
        alt_baro_ft=alt_baro_ft,
        ground_speed_kts=90.0,
        track_deg=180.0,
        squawk="1200",
        seen_pos_s=seen_pos_s,
        seen_s=seen_pos_s,
        rssi_db=-10.0,
        addr_type="adsb_icao",
        category=None,
        on_ground=on_ground,
    )


def test_find_nearest_returns_closest_aircraft() -> None:
    query = NearestQuery(lat=-41.29, lon=174.78, radius_km=15.0)
    near = _aircraft(hex="near", lat=-41.30, lon=174.77, flight="NEAR")
    far = _aircraft(hex="far", lat=-41.35, lon=174.90, flight="FAR")

    match = find_nearest([far, near], query)

    assert match is not None
    assert match.aircraft.hex == "near"


def test_find_nearest_filters_stale_on_ground_and_high_altitude() -> None:
    query = NearestQuery(
        lat=-41.29,
        lon=174.78,
        radius_km=15.0,
        max_alt_ft=5000,
        max_seen_pos_s=10.0,
    )
    aircraft = [
        _aircraft(hex="stale", lat=-41.30, lon=174.77, seen_pos_s=30.0),
        _aircraft(hex="ground", lat=-41.30, lon=174.77, on_ground=True),
        _aircraft(hex="high", lat=-41.30, lon=174.77, alt_baro_ft=9000),
        _aircraft(hex="good", lat=-41.30, lon=174.77, flight="GOOD"),
    ]

    match = find_nearest(aircraft, query)

    assert match is not None
    assert match.aircraft.hex == "good"


def test_describe_aircraft_uses_db_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIRCRAFT_DB_ENABLED", "true")
    monkeypatch.delenv("AIRCRAFT_DB_PREFIXES", raising=False)
    path = tmp_path / "aircraft_db.json.gz"
    with gzip.open(path, "wb") as handle:
        handle.write(json.dumps({"abc123": "CESSNA 172 Skyhawk"}).encode("utf-8"))
    monkeypatch.setenv("AIRCRAFT_DB_PATH", str(path))

    aircraft = _aircraft(hex="abc123", lat=-41.30, lon=174.77, type_code="C172")

    assert describe_aircraft(aircraft) == "Cessna 172 Skyhawk"


def test_build_summary_uses_flight_and_type() -> None:
    query = NearestQuery(lat=-41.29, lon=174.78)
    aircraft = _aircraft(
        hex="abc123",
        lat=-41.30,
        lon=174.77,
        flight="ZKNAX",
        type_code="C172",
    )
    match = find_nearest([aircraft], query)

    assert match is not None
    summary = build_summary(match)
    assert "ZKNAX" in summary
    assert "C172" in summary
    assert "1,200 feet" in summary
