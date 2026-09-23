"""Helpers for building synthetic binCraft payloads in tests."""

from __future__ import annotations

import struct
from typing import Any

import zstandard


def _write_c_string(buffer: bytearray, start: int, end: int, value: str) -> None:
    encoded = value.encode("ascii", errors="ignore")
    for index in range(start, end):
        buffer[index] = 0
    for offset, byte in enumerate(encoded):
        if start + offset >= end:
            break
        buffer[start + offset] = byte


def build_bincraft_payload(
    *,
    hex_id: int = 0xABC123,
    lat: float = -41.30,
    lon: float = 174.77,
    flight: str = "TEST1",
    registration: str = "ZK-TEST",
    type_code: str = "C172",
    on_ground: bool = False,
    alt_ft: int = 1200,
    addr_type_id: int = 0,
    category: int = 0x0A,
    rssi_raw: int = 100,
    include_zero_coords_record: bool = False,
) -> bytes:
    stride = 108
    header = bytearray(stride)
    struct.pack_into("<I", header, 8, stride)

    records: list[bytearray] = []
    if include_zero_coords_record:
        zero_record = bytearray(stride)
        records.append(zero_record)

    record = bytearray(stride)
    struct.pack_into(
        "<iiii",
        record,
        0,
        hex_id,
        0,
        int(lon * 1_000_000),
        int(lat * 1_000_000),
    )
    struct.pack_into("<H", record, 4, 50)
    struct.pack_into("<H", record, 6, 50)
    struct.pack_into("<h", record, 16, 4)  # baro_rate at s16[8]
    struct.pack_into("<h", record, 20, alt_ft // 25)  # baro_alt at s16[10]
    record[73] = 0x10  # alt_baro valid
    struct.pack_into("<H", record, 32, 0x1200)
    struct.pack_into("<h", record, 34, 900)
    struct.pack_into("<h", record, 40, 16_200)
    record[64] = category
    record[67] = (addr_type_id << 4) & 0xF0
    record[68] = 0x01 if on_ground else 0x00
    record[86] = rssi_raw
    _write_c_string(record, 78, 87, flight)
    _write_c_string(record, 88, 92, type_code)
    _write_c_string(record, 92, 104, registration)
    records.append(record)

    return bytes(header) + b"".join(bytes(item) for item in records)


def build_compressed_bincraft_payload(**kwargs: Any) -> bytes:
    payload = build_bincraft_payload(**kwargs)
    return zstandard.ZstdCompressor().compress(payload)
