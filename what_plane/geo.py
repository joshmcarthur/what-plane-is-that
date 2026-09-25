"""Geodesy helpers for nearest-aircraft selection."""

from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_RADIUS_KM = 6371.0

CARDINALS = (
    "north",
    "north-east",
    "east",
    "south-east",
    "south",
    "south-west",
    "west",
    "north-west",
)


@dataclass(frozen=True)
class BoundingBox:
    south: float
    north: float
    west: float
    east: float

    def as_api_param(self) -> str:
        return f"{self.south},{self.north},{self.west},{self.east}"


def bounding_box(lat: float, lon: float, radius_km: float) -> BoundingBox:
    lat_delta = radius_km / 111.0
    cos_lat = max(math.cos(math.radians(lat)), 0.01)
    lon_delta = radius_km / (111.0 * cos_lat)
    return BoundingBox(
        south=lat - lat_delta,
        north=lat + lat_delta,
        west=lon - lon_delta,
        east=lon + lon_delta,
    )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(d_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    d_lon = math.radians(lon2 - lon1)

    y = math.sin(d_lon) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(
        lat2_rad
    ) * math.cos(d_lon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def cardinal_direction(bearing: float) -> str:
    index = int((bearing + 22.5) // 45) % 8
    return CARDINALS[index]


FT_TO_M = 0.3048


def elevation_deg(
    distance_km: float,
    altitude_ft: float,
    observer_alt_m: float = 0.0,
) -> float:
    alt_m = altitude_ft * FT_TO_M - observer_alt_m
    return math.degrees(math.atan2(alt_m, distance_km * 1000.0))


def format_distance_km(distance_km: float) -> str:
    if distance_km < 1:
        metres = int(distance_km * 1000)
        return f"{metres} metres"
    if distance_km < 10:
        return f"{distance_km:.1f} kilometres"
    return f"{round(distance_km)} kilometres"
