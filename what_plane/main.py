"""HTTP API for finding the nearest aircraft via ADS-B Exchange."""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from what_plane.adsbexchange import AdsbExchangeClient, FetchResult
from what_plane.aircraft_db import (
    ensure_aircraft_db,
    get_db_status,
    lookup_aircraft_name,
)
from what_plane.cache import AdsbFetchCache, cache_ttl_seconds
from what_plane.config import ObserverConfig, load_observer_config
from what_plane.geo import bounding_box, cardinal_direction, format_distance_km
from what_plane.nearest import build_summary, find_nearest

client = AdsbExchangeClient()
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
    config: ObserverConfig,
    aircraft_in_box: int,
) -> dict[str, Any]:
    return {
        "found": False,
        "lat": config.lat,
        "lng": config.lng,
        "radius_km": config.radius_km,
        "aircraft_in_box": aircraft_in_box,
        "summary": "I don't see any aircraft nearby right now.",
    }


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
    }


@app.get("/nearest")
async def nearest() -> JSONResponse:
    global last_fetch

    config = _require_observer_config()
    box = bounding_box(config.lat, config.lng, config.radius_km)

    try:
        cached = await fetch_cache.fetch(client, box)
        last_fetch = cached
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch aircraft data from ADS-B Exchange: {exc}",
        ) from exc

    query = config.as_nearest_query()
    match = find_nearest(cached.aircraft, query)

    if match is None:
        return JSONResponse(
            _not_found_response(
                config=config,
                aircraft_in_box=len(cached.aircraft),
            )
        )

    ac = match.aircraft
    return JSONResponse(
        {
            "found": True,
            "lat": config.lat,
            "lng": config.lng,
            "radius_km": config.radius_km,
            "aircraft_in_box": len(cached.aircraft),
            "flight": ac.flight or None,
            "registration": ac.registration or None,
            "type": ac.type_code or None,
            "type_name": lookup_aircraft_name(ac.hex),
            "hex": ac.hex,
            "altitude_ft": ac.alt_baro_ft,
            "ground_speed_kts": round(ac.ground_speed_kts, 1),
            "heading_deg": round(ac.track_deg, 1),
            "distance_km": round(match.distance_km, 2),
            "bearing_deg": round(match.bearing_deg, 1),
            "direction": cardinal_direction(match.bearing_deg),
            "distance_text": format_distance_km(match.distance_km),
            "seen_pos_seconds_ago": ac.seen_pos_s,
            "seen_seconds_ago": ac.seen_s,
            "squawk": ac.squawk,
            "rssi_db": round(ac.rssi_db, 1),
            "summary": build_summary(match),
            "fetched_at": cached.fetched_at,
        }
    )


def main() -> None:  # pragma: no cover - CLI entrypoint
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "1320"))
    uvicorn.run("what_plane.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":  # pragma: no cover
    main()
