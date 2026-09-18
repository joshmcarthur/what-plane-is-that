"""Pick the nearest aircraft to an observer."""

from __future__ import annotations

from dataclasses import dataclass

from what_plane.aircraft_db import lookup_aircraft_name
from what_plane.bincraft import Aircraft
from what_plane.geo import (
    bearing_deg,
    cardinal_direction,
    format_distance_km,
    haversine_km,
)


@dataclass(frozen=True)
class NearestMatch:
    aircraft: Aircraft
    distance_km: float
    bearing_deg: float


@dataclass(frozen=True)
class NearestQuery:
    lat: float
    lon: float
    radius_km: float = 15.0
    max_alt_ft: int = 15_000
    max_seen_pos_s: float = 20.0


def find_nearest(aircraft: list[Aircraft], query: NearestQuery) -> NearestMatch | None:
    best: NearestMatch | None = None

    for ac in aircraft:
        if ac.seen_pos_s > query.max_seen_pos_s:
            continue
        if ac.on_ground:
            continue
        if ac.alt_baro_ft is not None and ac.alt_baro_ft > query.max_alt_ft:
            continue

        distance_km = haversine_km(query.lat, query.lon, ac.lat, ac.lon)
        if distance_km > query.radius_km:
            continue

        candidate = NearestMatch(
            aircraft=ac,
            distance_km=distance_km,
            bearing_deg=bearing_deg(query.lat, query.lon, ac.lat, ac.lon),
        )

        if best is None:
            best = candidate
            continue

        if candidate.distance_km < best.distance_km:
            best = candidate
            continue

        if candidate.distance_km == best.distance_km:
            candidate_alt = candidate.aircraft.alt_baro_ft or 99_999
            best_alt = best.aircraft.alt_baro_ft or 99_999
            if candidate_alt < best_alt:
                best = candidate

    return best


def describe_aircraft(ac: Aircraft) -> str:
    name = lookup_aircraft_name(ac.hex)
    if name:
        return name
    if ac.type_code:
        return ac.type_code
    if ac.registration:
        return ac.registration
    return "aircraft"


def build_summary(match: NearestMatch) -> str:
    ac = match.aircraft
    direction = cardinal_direction(match.bearing_deg)
    distance = format_distance_km(match.distance_km)
    aircraft_desc = describe_aircraft(ac)

    if ac.flight:
        headline = ac.flight
    elif ac.registration:
        headline = ac.registration
    else:
        headline = f"aircraft {ac.hex}"

    if ac.alt_baro_ft is None:
        altitude = "unknown altitude"
    else:
        altitude = f"{ac.alt_baro_ft:,} feet"

    return (
        f"{headline}, a {aircraft_desc}, at {altitude}, {distance} to the {direction}"
    )
