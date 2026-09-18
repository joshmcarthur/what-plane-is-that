"""Fetch, cache, and lookup human-readable aircraft names by hex id."""

from __future__ import annotations

import gzip
import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_URL = (
    "https://raw.githubusercontent.com/wiedehopf/tar1090-db/csv/aircraft.csv.gz"
)
DEFAULT_CACHE_DIR = Path(".cache/what-plane")
CACHE_FILENAME = "aircraft_db.json.gz"
META_FILENAME = "aircraft_db.meta.json"

_ensure_done = False
_resolved_db_path: Path | None = None


@dataclass(frozen=True)
class AircraftDbStatus:
    enabled: bool
    loaded: bool
    prefixes: tuple[str, ...]
    entries: int
    cache_path: str | None
    source_url: str | None
    error: str | None


def _normalize_hex(hex_id: str) -> str:
    return hex_id.strip().lower().removeprefix("~")


def format_aircraft_name(description: str) -> str:
    """Turn database descriptions like 'CESSNA 172 Skyhawk' into TTS-friendly text."""
    cleaned = " ".join(description.split())
    if not cleaned:
        return cleaned
    return cleaned.title()


def parse_registration_prefixes(raw: str) -> list[str]:
    prefixes: list[str] = []
    for part in raw.split(","):
        prefix = part.strip().upper().replace("-", "")
        if prefix and prefix not in prefixes:
            prefixes.append(prefix)
    return prefixes


def registration_matches(registration: str, prefixes: list[str]) -> bool:
    normalized = registration.strip().upper().replace("-", "")
    return any(normalized.startswith(prefix) for prefix in prefixes)


def build_slice_from_payload(payload: bytes, prefixes: list[str]) -> dict[str, str]:
    csv_payload = gzip.decompress(payload)
    db: dict[str, str] = {}

    for raw_line in csv_payload.decode("utf-8", errors="replace").splitlines():
        parts = raw_line.strip().split(";")
        if len(parts) < 5:
            continue

        hex_id = parts[0].strip().lower()
        registration = parts[1].strip()
        description = parts[4].strip()
        if not hex_id or not description:
            continue
        if not registration_matches(registration, prefixes):
            continue

        db[hex_id] = description

    return db


def fetch_slice(
    source_url: str,
    prefixes: list[str],
    *,
    timeout_s: float = 60.0,
) -> dict[str, str]:
    with httpx.Client(timeout=timeout_s) as client:
        response = client.get(source_url)
        response.raise_for_status()
    return build_slice_from_payload(response.content, prefixes)


def write_slice_cache(
    cache_path: Path,
    meta_path: Path,
    db: dict[str, str],
    *,
    prefixes: list[str],
    source_url: str,
) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(db, separators=(",", ":"), sort_keys=True).encode("utf-8")
    with gzip.open(cache_path, "wb") as handle:
        handle.write(encoded)

    meta = {
        "prefixes": prefixes,
        "source_url": source_url,
        "entry_count": len(db),
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _read_meta(meta_path: Path) -> dict[str, Any] | None:
    if not meta_path.is_file():
        return None
    try:
        raw = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return raw if isinstance(raw, dict) else None


def _cache_matches(meta_path: Path, cache_path: Path, prefixes: list[str]) -> bool:
    if not cache_path.is_file():
        return False

    meta = _read_meta(meta_path)
    if meta is None:
        return False

    cached_prefixes = meta.get("prefixes")
    if not isinstance(cached_prefixes, list):
        return False

    normalized = [str(prefix).upper() for prefix in cached_prefixes]
    return normalized == prefixes


def _load_db_path(path: Path) -> dict[str, str]:
    if path.suffix == ".gz" or path.name.endswith(".json.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return _validate_db(json.load(handle))
    with path.open(encoding="utf-8") as handle:
        return _validate_db(json.load(handle))


def _validate_db(raw: object) -> dict[str, str]:
    if not isinstance(raw, dict):
        msg = "Aircraft DB slice must be a JSON object keyed by hex id"
        raise ValueError(msg)

    db: dict[str, str] = {}
    for hex_id, description in raw.items():
        if not isinstance(hex_id, str) or not isinstance(description, str):
            continue
        normalized = _normalize_hex(hex_id)
        cleaned = description.strip()
        if normalized and cleaned:
            db[normalized] = cleaned
    return db


def reset_aircraft_db_state() -> None:
    global _ensure_done, _resolved_db_path
    _ensure_done = False
    _resolved_db_path = None
    get_aircraft_db.cache_clear()
    get_db_status.cache_clear()


def ensure_aircraft_db() -> None:
    global _ensure_done, _resolved_db_path

    if _ensure_done:
        return
    _ensure_done = True

    if os.getenv("AIRCRAFT_DB_ENABLED", "true").lower() in {"0", "false", "no"}:
        return

    explicit_path = os.getenv("AIRCRAFT_DB_PATH")
    if explicit_path:
        path = Path(explicit_path)
        if path.is_file():
            _resolved_db_path = path
        else:
            logger.warning("AIRCRAFT_DB_PATH does not exist: %s", path)
        return

    prefixes = parse_registration_prefixes(os.getenv("AIRCRAFT_DB_PREFIXES", ""))
    if not prefixes:
        logger.info("AIRCRAFT_DB_PREFIXES is empty; aircraft name lookup disabled")
        return

    source_url = os.getenv("AIRCRAFT_DB_SOURCE_URL", DEFAULT_SOURCE_URL)
    cache_dir = Path(os.getenv("AIRCRAFT_DB_CACHE_DIR", str(DEFAULT_CACHE_DIR)))
    cache_path = cache_dir / CACHE_FILENAME
    meta_path = cache_dir / META_FILENAME

    if _cache_matches(meta_path, cache_path, prefixes):
        _resolved_db_path = cache_path
        logger.info(
            "Using cached aircraft DB at %s (%s prefixes)",
            cache_path,
            ",".join(prefixes),
        )
        return

    try:
        db = fetch_slice(source_url, prefixes)
        write_slice_cache(
            cache_path,
            meta_path,
            db,
            prefixes=prefixes,
            source_url=source_url,
        )
        _resolved_db_path = cache_path
        logger.info(
            "Built aircraft DB cache at %s with %s entries for prefixes %s",
            cache_path,
            len(db),
            ",".join(prefixes),
        )
    except Exception:
        logger.exception(
            "Failed to fetch aircraft DB for prefixes %s",
            ",".join(prefixes),
        )
        if cache_path.is_file():
            logger.warning("Falling back to stale aircraft DB cache at %s", cache_path)
            _resolved_db_path = cache_path


@lru_cache(maxsize=1)
def get_aircraft_db() -> dict[str, str] | None:
    ensure_aircraft_db()
    if _resolved_db_path is None or not _resolved_db_path.is_file():
        return None
    return _load_db_path(_resolved_db_path)


@lru_cache(maxsize=1)
def get_db_status() -> AircraftDbStatus:
    ensure_aircraft_db()

    enabled = os.getenv("AIRCRAFT_DB_ENABLED", "true").lower() not in {
        "0",
        "false",
        "no",
    }
    prefixes = tuple(parse_registration_prefixes(os.getenv("AIRCRAFT_DB_PREFIXES", "")))
    source_url = os.getenv("AIRCRAFT_DB_SOURCE_URL", DEFAULT_SOURCE_URL)
    cache_path = str(_resolved_db_path) if _resolved_db_path else None

    if not enabled:
        return AircraftDbStatus(
            enabled=False,
            loaded=False,
            prefixes=prefixes,
            entries=0,
            cache_path=cache_path,
            source_url=source_url,
            error=None,
        )

    db = get_aircraft_db()
    if db is None:
        error = None
        if prefixes and _resolved_db_path is None:
            error = "aircraft database unavailable"
        return AircraftDbStatus(
            enabled=True,
            loaded=False,
            prefixes=prefixes,
            entries=0,
            cache_path=cache_path,
            source_url=source_url,
            error=error,
        )

    return AircraftDbStatus(
        enabled=True,
        loaded=True,
        prefixes=prefixes,
        entries=len(db),
        cache_path=cache_path,
        source_url=source_url,
        error=None,
    )


def lookup_aircraft_name(hex_id: str) -> str | None:
    db = get_aircraft_db()
    if db is None:
        return None

    description = db.get(_normalize_hex(hex_id))
    if description is None:
        return None
    return format_aircraft_name(description)
