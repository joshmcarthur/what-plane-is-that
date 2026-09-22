"""Tests for nearest-aircraft selection."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest
from what_plane.adsbdb import Airport, FlightRoute
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


def test_find_nearest_ignores_aircraft_outside_radius() -> None:
    query = NearestQuery(lat=-41.29, lon=174.78, radius_km=1.0)
    far = _aircraft(hex="far", lat=-42.0, lon=175.5, flight="FAR")

    assert find_nearest([far], query) is None


def test_find_nearest_prefers_lower_altitude_on_distance_tie() -> None:
    query = NearestQuery(lat=-41.29, lon=174.78, radius_km=15.0)
    low = _aircraft(
        hex="low",
        lat=-41.30,
        lon=174.77,
        alt_baro_ft=1000,
        flight="LOW",
    )
    high = _aircraft(
        hex="high",
        lat=-41.30,
        lon=174.77,
        alt_baro_ft=5000,
        flight="HIGH",
    )

    match = find_nearest([high, low], query)

    assert match is not None
    assert match.aircraft.hex == "low"


def test_describe_aircraft_falls_back_to_type_and_registration() -> None:
    by_type = _aircraft(hex="abc123", lat=-41.30, lon=174.77, type_code="C172")
    by_registration = _aircraft(
        hex="def456",
        lat=-41.30,
        lon=174.77,
        type_code="",
        registration="ZK-TEST",
    )
    generic = _aircraft(
        hex="999999",
        lat=-41.30,
        lon=174.77,
        type_code="",
        registration="",
    )

    assert describe_aircraft(by_type) == "C172"
    assert describe_aircraft(by_registration) == "ZK-TEST"
    assert describe_aircraft(generic) == "aircraft"


def test_build_summary_uses_registration_when_flight_missing() -> None:
    query = NearestQuery(lat=-41.29, lon=174.78)
    aircraft = _aircraft(
        hex="abc123",
        lat=-41.30,
        lon=174.77,
        registration="ZK-NAX",
        type_code="C172",
    )
    match = find_nearest([aircraft], query)

    assert match is not None
    summary = build_summary(match)
    assert summary.startswith("ZK-NAX,")


def test_build_summary_uses_hex_and_unknown_altitude() -> None:
    query = NearestQuery(lat=-41.29, lon=174.78)
    aircraft = _aircraft(
        hex="abc123",
        lat=-41.30,
        lon=174.77,
        alt_baro_ft=None,
    )
    match = find_nearest([aircraft], query)

    assert match is not None
    summary = build_summary(match)
    assert "aircraft abc123" in summary
    assert "unknown altitude" in summary


def test_build_summary_includes_route_when_available() -> None:
    query = NearestQuery(lat=-41.29, lon=174.78)
    aircraft = _aircraft(
        hex="abc123",
        lat=-41.30,
        lon=174.77,
        flight="ANZ362M",
        type_code="AT76",
    )
    match = find_nearest([aircraft], query)
    route = FlightRoute(
        callsign="ANZ362M",
        airline="Air New Zealand",
        origin=Airport(
            icao="NZCH",
            iata="CHC",
            name="Christchurch International Airport",
            municipality="Christchurch",
        ),
        destination=Airport(
            icao="NZWN",
            iata="WLG",
            name="Wellington International Airport",
            municipality="Wellington",
        ),
    )

    assert match is not None
    summary = build_summary(match, route)
    assert "ANZ362M" in summary
    assert "Christchurch" in summary
    assert "Wellington" in summary
    assert "Air New Zealand" in summary
