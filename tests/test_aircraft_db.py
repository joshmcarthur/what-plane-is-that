"""Tests for aircraft metadata lookup."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest
from what_plane import aircraft_db


@pytest.fixture
def sample_db_path(tmp_path: Path) -> Path:
    payload = {"abc123": "CESSNA 172 Skyhawk", "def456": "PIPER PA-28-180"}
    path = tmp_path / "aircraft_db.json.gz"
    encoded = json.dumps(payload).encode("utf-8")
    with gzip.open(path, "wb") as handle:
        handle.write(encoded)
    return path


def test_format_aircraft_name_title_cases_description() -> None:
    assert (
        aircraft_db.format_aircraft_name("CESSNA 172 Skyhawk") == "Cessna 172 Skyhawk"
    )


def test_parse_registration_prefixes() -> None:
    assert aircraft_db.parse_registration_prefixes("ZK, VH") == ["ZK", "VH"]
    assert aircraft_db.parse_registration_prefixes("zk-") == ["ZK"]


def test_build_slice_from_payload_filters_by_prefix() -> None:
    csv_lines = "\n".join(
        [
            "abc123;ZK-TEST;C172;00;CESSNA 172 Skyhawk;;;",
            "def456;VH-TEST;C172;00;CESSNA 172 Skyhawk;;;",
            "999999;N12345;C172;00;CESSNA 172 Skyhawk;;;",
        ]
    )
    payload = gzip.compress(csv_lines.encode("utf-8"))

    db = aircraft_db.build_slice_from_payload(payload, ["ZK"])

    assert db == {"abc123": "CESSNA 172 Skyhawk"}


def test_lookup_aircraft_name_from_custom_path(
    sample_db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIRCRAFT_DB_ENABLED", "true")
    monkeypatch.setenv("AIRCRAFT_DB_PATH", str(sample_db_path))

    assert aircraft_db.lookup_aircraft_name("ABC123") == "Cessna 172 Skyhawk"
    assert aircraft_db.lookup_aircraft_name("missing") is None


def test_lookup_can_be_disabled(
    sample_db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIRCRAFT_DB_PATH", str(sample_db_path))
    monkeypatch.setenv("AIRCRAFT_DB_ENABLED", "false")

    assert aircraft_db.lookup_aircraft_name("ABC123") is None


def test_ensure_uses_existing_cache_when_prefixes_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir = tmp_path / "cache"
    cache_path = cache_dir / aircraft_db.CACHE_FILENAME
    meta_path = cache_dir / aircraft_db.META_FILENAME
    db = {"abc123": "CESSNA 172 Skyhawk"}
    aircraft_db.write_slice_cache(
        cache_path,
        meta_path,
        db,
        prefixes=["ZK"],
        source_url="https://example.test/aircraft.csv.gz",
    )

    monkeypatch.setenv("AIRCRAFT_DB_ENABLED", "true")
    monkeypatch.setenv("AIRCRAFT_DB_PREFIXES", "ZK")
    monkeypatch.setenv("AIRCRAFT_DB_CACHE_DIR", str(cache_dir))

    aircraft_db.ensure_aircraft_db()

    assert aircraft_db.lookup_aircraft_name("abc123") == "Cessna 172 Skyhawk"


def test_ensure_refetches_when_prefixes_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir = tmp_path / "cache"
    cache_path = cache_dir / aircraft_db.CACHE_FILENAME
    meta_path = cache_dir / aircraft_db.META_FILENAME
    aircraft_db.write_slice_cache(
        cache_path,
        meta_path,
        {"abc123": "CESSNA 172 Skyhawk"},
        prefixes=["ZK"],
        source_url="https://example.test/aircraft.csv.gz",
    )

    csv_payload = gzip.compress(b"def456;VH-ONE;C172;00;PIPER PA-28-180;;;\n")

    class FakeResponse:
        content = csv_payload

        @staticmethod
        def raise_for_status() -> None:
            return None

    class FakeClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def get(self, _url: str) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setenv("AIRCRAFT_DB_ENABLED", "true")
    monkeypatch.setenv("AIRCRAFT_DB_PREFIXES", "VH")
    monkeypatch.setenv("AIRCRAFT_DB_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("AIRCRAFT_DB_SOURCE_URL", "https://example.test/aircraft.csv.gz")
    monkeypatch.setattr(aircraft_db.httpx, "Client", FakeClient)

    aircraft_db.ensure_aircraft_db()

    assert aircraft_db.lookup_aircraft_name("def456") == "Piper Pa-28-180"
    assert aircraft_db.lookup_aircraft_name("abc123") is None
