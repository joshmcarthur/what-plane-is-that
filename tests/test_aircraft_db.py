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


def test_format_aircraft_name_returns_empty_string() -> None:
    assert aircraft_db.format_aircraft_name("   ") == ""


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


def test_build_slice_from_payload_skips_invalid_rows() -> None:
    csv_lines = "\n".join(
        [
            "short",
            ";ZK-TEST;C172;00;CESSNA 172 Skyhawk;;;",
            "abc123;ZK-TEST;C172;00;;;",
        ]
    )
    payload = gzip.compress(csv_lines.encode("utf-8"))

    assert aircraft_db.build_slice_from_payload(payload, ["ZK"]) == {}


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


def test_ensure_uses_explicit_db_path(
    sample_db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIRCRAFT_DB_ENABLED", "true")
    monkeypatch.setenv("AIRCRAFT_DB_PATH", str(sample_db_path))

    aircraft_db.ensure_aircraft_db()

    assert aircraft_db.lookup_aircraft_name("ABC123") == "Cessna 172 Skyhawk"


def test_ensure_warns_when_explicit_db_path_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = tmp_path / "missing.json.gz"
    monkeypatch.setenv("AIRCRAFT_DB_ENABLED", "true")
    monkeypatch.setenv("AIRCRAFT_DB_PATH", str(missing))

    aircraft_db.ensure_aircraft_db()
    status = aircraft_db.get_db_status()

    assert status.loaded is False
    assert status.error is None


def test_ensure_skips_lookup_when_prefixes_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIRCRAFT_DB_ENABLED", "true")
    monkeypatch.delenv("AIRCRAFT_DB_PATH", raising=False)
    monkeypatch.setenv("AIRCRAFT_DB_PREFIXES", "")

    aircraft_db.ensure_aircraft_db()
    status = aircraft_db.get_db_status()

    assert status.enabled is True
    assert status.loaded is False
    assert status.error is None


def test_ensure_falls_back_to_stale_cache_on_fetch_failure(
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

    class BrokenClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> BrokenClient:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def get(self, _url: str) -> object:
            raise RuntimeError("network down")

    monkeypatch.setenv("AIRCRAFT_DB_ENABLED", "true")
    monkeypatch.setenv("AIRCRAFT_DB_PREFIXES", "VH")
    monkeypatch.setenv("AIRCRAFT_DB_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("AIRCRAFT_DB_SOURCE_URL", "https://example.test/aircraft.csv.gz")
    monkeypatch.setattr(aircraft_db.httpx, "Client", BrokenClient)

    aircraft_db.ensure_aircraft_db()

    assert aircraft_db.lookup_aircraft_name("abc123") == "Cessna 172 Skyhawk"


def test_load_db_path_supports_plain_json(tmp_path: Path) -> None:
    path = tmp_path / "aircraft_db.json"
    path.write_text('{"abc123": "CESSNA 172 Skyhawk"}', encoding="utf-8")

    assert aircraft_db._load_db_path(path) == {"abc123": "CESSNA 172 Skyhawk"}


def test_validate_db_skips_invalid_entries() -> None:
    raw = {
        "abc123": "CESSNA 172 Skyhawk",
        123: "bad",
        "": "missing hex",
        "def456": 99,
    }

    assert aircraft_db._validate_db(raw) == {"abc123": "CESSNA 172 Skyhawk"}


def test_validate_db_rejects_non_object_payload() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        aircraft_db._validate_db(["not", "a", "dict"])


def test_cache_matches_rejects_invalid_meta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cache_path = cache_dir / aircraft_db.CACHE_FILENAME
    meta_path = cache_dir / aircraft_db.META_FILENAME
    cache_path.write_bytes(b"data")
    meta_path.write_text("not-json", encoding="utf-8")

    assert aircraft_db._cache_matches(meta_path, cache_path, ["ZK"]) is False


def test_cache_matches_rejects_prefix_mismatch(tmp_path: Path) -> None:
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

    assert aircraft_db._cache_matches(meta_path, cache_path, ["VH"]) is False


def test_get_db_status_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIRCRAFT_DB_ENABLED", "false")
    monkeypatch.setenv("AIRCRAFT_DB_PREFIXES", "ZK")

    status = aircraft_db.get_db_status()

    assert status.enabled is False
    assert status.loaded is False


def test_get_db_status_reports_unavailable_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> BrokenClient:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def get(self, _url: str) -> object:
            raise RuntimeError("network down")

    monkeypatch.setenv("AIRCRAFT_DB_ENABLED", "true")
    monkeypatch.setenv("AIRCRAFT_DB_PREFIXES", "ZK")
    monkeypatch.setenv("AIRCRAFT_DB_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("AIRCRAFT_DB_PATH", raising=False)
    monkeypatch.setattr(aircraft_db.httpx, "Client", BrokenClient)

    aircraft_db.reset_aircraft_db_state()
    aircraft_db.ensure_aircraft_db()

    status = aircraft_db.get_db_status()

    assert status.enabled is True
    assert status.loaded is False
    assert status.error == "aircraft database unavailable"


def test_get_db_status_reports_loaded_database(
    sample_db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIRCRAFT_DB_ENABLED", "true")
    monkeypatch.setenv("AIRCRAFT_DB_PATH", str(sample_db_path))

    status = aircraft_db.get_db_status()

    assert status.enabled is True
    assert status.loaded is True
    assert status.entries == 2
    assert status.error is None


def test_cache_matches_requires_cache_file(tmp_path: Path) -> None:
    meta_path = tmp_path / aircraft_db.META_FILENAME
    cache_path = tmp_path / aircraft_db.CACHE_FILENAME
    meta_path.write_text('{"prefixes": ["ZK"]}', encoding="utf-8")

    assert aircraft_db._cache_matches(meta_path, cache_path, ["ZK"]) is False


def test_read_meta_returns_none_when_file_missing(tmp_path: Path) -> None:
    meta_path = tmp_path / aircraft_db.META_FILENAME

    assert aircraft_db._read_meta(meta_path) is None


def test_read_meta_returns_none_for_invalid_json(tmp_path: Path) -> None:
    meta_path = tmp_path / aircraft_db.META_FILENAME
    meta_path.write_text("{", encoding="utf-8")

    assert aircraft_db._read_meta(meta_path) is None


def test_read_meta_returns_none_for_non_object_payload(tmp_path: Path) -> None:
    meta_path = tmp_path / aircraft_db.META_FILENAME
    meta_path.write_text('["ZK"]', encoding="utf-8")

    assert aircraft_db._read_meta(meta_path) is None


def test_cache_matches_rejects_non_list_prefixes(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cache_path = cache_dir / aircraft_db.CACHE_FILENAME
    meta_path = cache_dir / aircraft_db.META_FILENAME
    cache_path.write_bytes(b"data")
    meta_path.write_text('{"prefixes": "ZK"}', encoding="utf-8")

    assert aircraft_db._cache_matches(meta_path, cache_path, ["ZK"]) is False
