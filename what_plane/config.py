"""Site-specific configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from what_plane.nearest import NearestQuery


@dataclass(frozen=True)
class ObserverConfig:
    lat: float
    lng: float
    radius_km: float
    max_alt_ft: int
    max_seen_pos_s: float

    def as_nearest_query(self) -> NearestQuery:
        return NearestQuery(
            lat=self.lat,
            lon=self.lng,
            radius_km=self.radius_km,
            max_alt_ft=self.max_alt_ft,
            max_seen_pos_s=self.max_seen_pos_s,
        )


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        msg = f"{name} is required"
        raise ValueError(msg)
    return value.strip()


def _env_float(
    name: str,
    default: float,
    *,
    min_value: float,
    max_value: float,
) -> float:
    raw = os.getenv(name)
    value = default if raw is None or not raw.strip() else float(raw)

    if value < min_value or value > max_value:
        msg = f"{name} must be between {min_value} and {max_value}"
        raise ValueError(msg)
    return value


def _env_int(
    name: str,
    default: int,
    *,
    min_value: int,
    max_value: int,
) -> int:
    raw = os.getenv(name)
    value = default if raw is None or not raw.strip() else int(raw)

    if value < min_value or value > max_value:
        msg = f"{name} must be between {min_value} and {max_value}"
        raise ValueError(msg)
    return value


def load_observer_config() -> ObserverConfig:
    lat = float(_require_env("OBSERVER_LAT"))
    lng = float(_require_env("OBSERVER_LNG"))

    if lat < -90 or lat > 90:
        msg = "OBSERVER_LAT must be between -90 and 90"
        raise ValueError(msg)
    if lng < -180 or lng > 180:
        msg = "OBSERVER_LNG must be between -180 and 180"
        raise ValueError(msg)

    radius_km = _env_float(
        "NEAREST_RADIUS_KM",
        15.0,
        min_value=0.0,
        max_value=100.0,
    )
    if radius_km <= 0:
        msg = "NEAREST_RADIUS_KM must be greater than 0"
        raise ValueError(msg)

    max_seen_pos_s = _env_float(
        "NEAREST_MAX_SEEN_POS_S",
        20.0,
        min_value=0.0,
        max_value=120.0,
    )
    if max_seen_pos_s <= 0:
        msg = "NEAREST_MAX_SEEN_POS_S must be greater than 0"
        raise ValueError(msg)

    max_alt_ft = _env_int(
        "NEAREST_MAX_ALT_FT",
        15_000,
        min_value=1,
        max_value=60_000,
    )

    return ObserverConfig(
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        max_alt_ft=max_alt_ft,
        max_seen_pos_s=max_seen_pos_s,
    )
