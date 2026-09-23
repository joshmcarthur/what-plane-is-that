"""Look up airline flight routes from adsbdb by callsign."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_API_URL = "https://api.adsbdb.com/v0/callsign"
DEFAULT_CACHE_TTL_SECONDS = 300.0
DEFAULT_TIMEOUT_S = 10.0


@dataclass(frozen=True)
class Airport:
    icao: str
    iata: str | None
    name: str
    municipality: str | None


@dataclass(frozen=True)
class FlightRoute:
    callsign: str
    airline: str | None
    origin: Airport
    destination: Airport


def adsbdb_enabled() -> bool:
    return os.getenv("ADSBDB_ENABLED", "true").lower() not in {"0", "false", "no"}


def route_cache_ttl_seconds() -> float:
    return float(os.getenv("ADSBDB_CACHE_TTL_SECONDS", str(DEFAULT_CACHE_TTL_SECONDS)))


def _api_url() -> str:
    return os.getenv("ADSBDB_API_URL", DEFAULT_API_URL).rstrip("/")


def _timeout_s() -> float:
    return float(os.getenv("ADSBDB_TIMEOUT_S", str(DEFAULT_TIMEOUT_S)))


def normalize_callsign(callsign: str) -> str:
    return callsign.strip().upper()


def _parse_airport(raw: dict[str, Any]) -> Airport:
    return Airport(
        icao=str(raw.get("icao_code", "")),
        iata=raw.get("iata_code") or None,
        name=str(raw.get("name", "")),
        municipality=raw.get("municipality") or None,
    )


def parse_callsign_response(payload: object) -> FlightRoute | None:
    if not isinstance(payload, dict):
        return None

    response = payload.get("response")
    if response == "unknown callsign" or not isinstance(response, dict):
        return None

    flightroute = response.get("flightroute")
    if not isinstance(flightroute, dict):
        return None

    origin_raw = flightroute.get("origin")
    destination_raw = flightroute.get("destination")
    if not isinstance(origin_raw, dict) or not isinstance(destination_raw, dict):
        return None

    airline_raw = flightroute.get("airline")
    airline_name = None
    if isinstance(airline_raw, dict):
        airline_name = airline_raw.get("name") or None

    callsign = flightroute.get("callsign")
    if not isinstance(callsign, str) or not callsign.strip():
        return None

    return FlightRoute(
        callsign=callsign.strip(),
        airline=airline_name,
        origin=_parse_airport(origin_raw),
        destination=_parse_airport(destination_raw),
    )


def airport_label(airport: Airport) -> str:
    if airport.municipality:
        return airport.municipality
    if airport.iata:
        return airport.iata
    if airport.name:
        return airport.name
    return airport.icao


def route_to_dict(route: FlightRoute) -> dict[str, Any]:
    return {
        "callsign": route.callsign,
        "airline": route.airline,
        "origin_icao": route.origin.icao or None,
        "origin_iata": route.origin.iata,
        "origin_name": route.origin.name or None,
        "origin_municipality": route.origin.municipality,
        "destination_icao": route.destination.icao or None,
        "destination_iata": route.destination.iata,
        "destination_name": route.destination.name or None,
        "destination_municipality": route.destination.municipality,
    }


@dataclass
class _RouteCacheEntry:
    route: FlightRoute | None
    expires_at: float


class AdsbDbClient:
    def __init__(
        self,
        api_url: str | None = None,
        timeout_s: float | None = None,
        cache_ttl_seconds: float | None = None,
    ) -> None:
        self.api_url = (api_url or _api_url()).rstrip("/")
        self.timeout_s = timeout_s if timeout_s is not None else _timeout_s()
        self.cache_ttl_seconds = (
            cache_ttl_seconds
            if cache_ttl_seconds is not None
            else route_cache_ttl_seconds()
        )
        self._cache: dict[str, _RouteCacheEntry] = {}

    def clear_cache(self) -> None:
        self._cache.clear()

    def _get_cached(self, callsign: str) -> tuple[bool, FlightRoute | None]:
        entry = self._cache.get(callsign)
        if entry is None:
            return False, None
        if entry.expires_at <= time.time():
            del self._cache[callsign]
            return False, None
        return True, entry.route

    def _set_cached(self, callsign: str, route: FlightRoute | None) -> None:
        self._cache[callsign] = _RouteCacheEntry(
            route=route,
            expires_at=time.time() + self.cache_ttl_seconds,
        )

    async def lookup_route(self, callsign: str) -> FlightRoute | None:
        normalized = normalize_callsign(callsign)
        if not normalized:
            return None

        hit, cached = self._get_cached(normalized)
        if hit:
            return cached

        url = f"{self.api_url}/{normalized}"
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            response = await client.get(url)
            response.raise_for_status()

        route = parse_callsign_response(response.json())
        self._set_cached(normalized, route)
        return route
