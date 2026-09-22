"""Tests for binCraft decoding."""

from __future__ import annotations

import struct

from tests.bincraft_fixtures import (
    build_bincraft_payload,
    build_compressed_bincraft_payload,
)
from what_plane.bincraft import _read_c_string, decode_bincraft


def test_read_c_string_stops_at_null_and_skips_non_printable() -> None:
    data = b"AB\x00CD" + bytes([20, 65])

    assert _read_c_string(data, 0, 6) == "AB"


def test_decode_bincraft_rejects_short_payload() -> None:
    assert decode_bincraft(b"short", zstd_compressed=False) == []


def test_decode_bincraft_rejects_invalid_stride() -> None:
    payload = b"\x00" * 8 + b"\xff\x00\x00\x00" + b"\x00" * 20
    assert decode_bincraft(payload, zstd_compressed=False) == []


def test_decode_bincraft_parses_airborne_record() -> None:
    aircraft = decode_bincraft(build_bincraft_payload(), zstd_compressed=False)

    assert len(aircraft) == 1
    ac = aircraft[0]
    assert ac.hex == "abc123"
    assert ac.flight == "TEST1"
    assert ac.registration == "ZK-TEST"
    assert ac.type_code == "C172"
    assert ac.lat == -41.30
    assert ac.lon == 174.77
    assert ac.alt_baro_ft == 1200
    assert ac.on_ground is False
    assert ac.addr_type == "adsb_icao"
    assert ac.category == "0A"


def test_decode_bincraft_skips_zero_coordinate_records() -> None:
    aircraft = decode_bincraft(
        build_bincraft_payload(include_zero_coords_record=True),
        zstd_compressed=False,
    )

    assert len(aircraft) == 1
    assert aircraft[0].flight == "TEST1"


def test_decode_bincraft_handles_on_ground_and_unknown_addr_type() -> None:
    aircraft = decode_bincraft(
        build_bincraft_payload(on_ground=True, addr_type_id=13),
        zstd_compressed=False,
    )

    assert len(aircraft) == 1
    ac = aircraft[0]
    assert ac.on_ground is True
    assert ac.alt_baro_ft is None
    assert ac.addr_type == "unknown"


def test_decode_bincraft_handles_zstd_payload() -> None:
    payload = build_compressed_bincraft_payload()
    aircraft = decode_bincraft(payload, zstd_compressed=True)

    assert len(aircraft) == 1
    assert aircraft[0].flight == "TEST1"


def test_decode_bincraft_ignores_truncated_tail_record() -> None:
    payload = build_bincraft_payload() + b"\x00" * 20

    aircraft = decode_bincraft(payload, zstd_compressed=False)

    assert len(aircraft) == 1


def test_decode_bincraft_reads_baro_altitude_from_s16_10() -> None:
    stride = 108
    record = bytearray(stride)
    struct.pack_into("<I", record, 0, 0x00C87F39)
    struct.pack_into("<i", record, 8, int(174.78 * 1_000_000))
    struct.pack_into("<i", record, 12, int(-41.15 * 1_000_000))
    struct.pack_into("<h", record, 16, 4)  # baro_rate: 32 fpm when decoded
    struct.pack_into("<h", record, 20, 188)  # baro_alt: 4,700 ft when decoded
    record[68] = 0  # airborne
    record[73] = 0x10  # alt_baro valid

    header = bytearray(stride)
    struct.pack_into("<I", header, 8, stride)
    payload = bytes(header) + bytes(record)
    aircraft = decode_bincraft(payload, zstd_compressed=False)

    assert len(aircraft) == 1
    assert aircraft[0].alt_baro_ft == 4700
