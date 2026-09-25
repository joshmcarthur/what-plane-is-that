"""HTTP API for finding the nearest aircraft via ADS-B Exchange."""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from what_plane.adsbdb import AdsbDbClient, adsbdb_enabled, route_to_dict
from what_plane.adsbexchange import AdsbExchangeClient, FetchResult
from what_plane.aircraft_db import (
    ensure_aircraft_db,
    get_db_status,
    lookup_aircraft_name,
)
from what_plane.cache import AdsbFetchCache, cache_ttl_seconds
from what_plane.config import ObserverConfig, load_observer_config
from what_plane.geo import (
    bounding_box,
    cardinal_direction,
    elevation_deg,
    format_distance_km,
)
from what_plane.nearest import NearestMatch, NearestQuery, build_summary, find_nearest

WEB_DIR = Path(__file__).resolve().parent / "web"

client = AdsbExchangeClient()
adsbdb_client = AdsbDbClient()
fetch_cache = AdsbFetchCache(cache_ttl_seconds())
started_at = time.time()
last_fetch: FetchResult | None = None
observer_config: ObserverConfig | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global observer_config

    ensure_aircraft_db()
    observer_config = load_observer_config()
    yield


app = FastAPI(
    title="what-plane",
    description="Return the nearest aircraft near a configured observer location.",
    version="0.1.0",
    lifespan=lifespan,
)


def _require_observer_config() -> ObserverConfig:
    if observer_config is None:
        raise HTTPException(
            status_code=503,
            detail="Observer location is not configured",
        )
    return observer_config


def _not_found_response(
    *,
    lat: float,
    lng: float,
    radius_km: float,
    aircraft_in_box: int,
) -> dict[str, Any]:
    return {
        "found": False,
        "lat": lat,
        "lng": lng,
        "radius_km": radius_km,
        "aircraft_in_box": aircraft_in_box,
        "summary": "I don't see any aircraft nearby right now.",
    }


def _found_response(
    *,
    match: NearestMatch,
    lat: float,
    lng: float,
    radius_km: float,
    aircraft_in_box: int,
    fetched_at: float,
    route: Any | None,
) -> dict[str, Any]:
    ac = match.aircraft
    return {
        "found": True,
        "lat": lat,
        "lng": lng,
        "radius_km": radius_km,
        "aircraft_in_box": aircraft_in_box,
        "flight": ac.flight.strip() if ac.flight else None,
        "registration": ac.registration or None,
        "type": ac.type_code or None,
        "type_name": lookup_aircraft_name(ac.hex),
        "hex": ac.hex,
        "altitude_ft": ac.alt_baro_ft,
        "ground_speed_kts": round(ac.ground_speed_kts, 1),
        "heading_deg": round(ac.track_deg, 1),
        "distance_km": round(match.distance_km, 2),
        "bearing_deg": round(match.bearing_deg, 1),
        "elevation_deg": None
        if ac.alt_baro_ft is None
        else round(elevation_deg(match.distance_km, ac.alt_baro_ft), 1),
        "direction": cardinal_direction(match.bearing_deg),
        "distance_text": format_distance_km(match.distance_km),
        "seen_pos_seconds_ago": ac.seen_pos_s,
        "seen_seconds_ago": ac.seen_s,
        "squawk": ac.squawk,
        "rssi_db": round(ac.rssi_db, 1),
        "route": route_to_dict(route) if route is not None else None,
        "summary": build_summary(match, route),
        "fetched_at": fetched_at,
    }


async def _lookup_route(flight: str | None) -> Any | None:
    if not adsbdb_enabled() or not flight:
        return None
    try:
        return await adsbdb_client.lookup_route(flight)
    except Exception:
        return None


async def _nearest_lookup(
    lat: float,
    lng: float,
    config: ObserverConfig,
) -> dict[str, Any]:
    global last_fetch

    box = bounding_box(lat, lng, config.radius_km)

    try:
        cached = await fetch_cache.fetch(client, box)
        last_fetch = cached
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch aircraft data from ADS-B Exchange: {exc}",
        ) from exc

    query = NearestQuery(
        lat=lat,
        lon=lng,
        radius_km=config.radius_km,
        max_alt_ft=config.max_alt_ft,
        max_seen_pos_s=config.max_seen_pos_s,
    )
    match = find_nearest(cached.aircraft, query)

    if match is None:
        return _not_found_response(
            lat=lat,
            lng=lng,
            radius_km=config.radius_km,
            aircraft_in_box=len(cached.aircraft),
        )

    route = await _lookup_route(match.aircraft.flight)
    return _found_response(
        match=match,
        lat=lat,
        lng=lng,
        radius_km=config.radius_km,
        aircraft_in_box=len(cached.aircraft),
        fetched_at=cached.fetched_at,
        route=route,
    )


@app.get("/health")
async def health() -> dict[str, Any]:
    db_status = get_db_status()
    config = observer_config

    return {
        "ok": True,
        "source": "adsbexchange",
        "uptime_seconds": int(time.time() - started_at),
        "cache_ttl_seconds": cache_ttl_seconds(),
        "last_fetch_at": last_fetch.fetched_at if last_fetch else None,
        "last_aircraft_count": len(last_fetch.aircraft) if last_fetch else 0,
        "observer": None
        if config is None
        else {
            "lat": config.lat,
            "lng": config.lng,
            "radius_km": config.radius_km,
            "max_alt_ft": config.max_alt_ft,
            "max_seen_pos_s": config.max_seen_pos_s,
        },
        "aircraft_db": {
            "enabled": db_status.enabled,
            "loaded": db_status.loaded,
            "prefixes": list(db_status.prefixes),
            "entries": db_status.entries,
            "cache_path": db_status.cache_path,
            "error": db_status.error,
        },
        "adsbdb": {
            "enabled": adsbdb_enabled(),
        },
    }


@app.get("/nearest")
async def nearest() -> JSONResponse:
    config = _require_observer_config()
    body = await _nearest_lookup(config.lat, config.lng, config)
    return JSONResponse(body)


@app.get("/nearest/at")
async def nearest_at(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
) -> JSONResponse:
    config = _require_observer_config()
    body = await _nearest_lookup(lat, lng, config)
    return JSONResponse(body)


@app.get("/", include_in_schema=False)
async def web_index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIR), name="web")


def main() -> None:  # pragma: no cover - CLI entrypoint
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "1320"))
    uvicorn.run("what_plane.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":  # pragma: no cover
    main()
