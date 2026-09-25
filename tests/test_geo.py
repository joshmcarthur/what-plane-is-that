"""Tests for geodesy helpers."""

from __future__ import annotations

from what_plane.geo import (
    bounding_box,
    cardinal_direction,
    elevation_deg,
    format_distance_km,
    haversine_km,
)


def test_bounding_box_as_api_param() -> None:
    box = bounding_box(-41.29, 174.78, 15.0)
    assert box.as_api_param() == (f"{box.south},{box.north},{box.west},{box.east}")


def test_haversine_km_same_point_is_zero() -> None:
    assert haversine_km(-41.29, 174.78, -41.29, 174.78) == 0.0


def test_haversine_km_known_distance() -> None:
    # Christchurch to Wellington is roughly 300 km.
    distance = haversine_km(-43.532, 172.636, -41.286, 174.776)
    assert 290 < distance < 320


def test_cardinal_direction() -> None:
    assert cardinal_direction(0) == "north"
    assert cardinal_direction(90) == "east"
    assert cardinal_direction(180) == "south"
    assert cardinal_direction(225) == "south-west"


def test_format_distance_km() -> None:
    assert format_distance_km(0.5) == "500 metres"
    assert format_distance_km(3.2) == "3.2 kilometres"
    assert format_distance_km(12.4) == "12 kilometres"


def test_elevation_deg_nearby_level_flight_is_a_small_angle() -> None:
    angle = elevation_deg(3.2, 1200)
    assert 6 < angle < 7


def test_elevation_deg_overhead_is_near_vertical() -> None:
    angle = elevation_deg(0.01, 10_000)
    assert angle > 89


def test_elevation_deg_zero_distance_is_plus_or_minus_90() -> None:
    assert elevation_deg(0.0, 1200) == 90.0
    assert elevation_deg(0.0, -100) == -90.0
    assert elevation_deg(0.0, 0) == 0.0


def test_elevation_deg_subtracts_observer_altitude() -> None:
    from_sea_level = elevation_deg(1.0, 1000)
    from_hill = elevation_deg(1.0, 1000, observer_alt_m=100)
    assert from_hill < from_sea_level
