"""Decode ADS-B Exchange binCraft snapshots (optionally zstd-compressed)."""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass

import zstandard

ADDRTYPE_NAMES = {
    0: "adsb_icao",
    1: "adsb_icao_nt",
    2: "adsr_icao",
    3: "tisb_icao",
    4: "adsc",
    5: "mlat",
    6: "other",
    7: "mode_s",
    8: "adsb_other",
    9: "adsr_other",
    10: "tisb_trackfile",
    11: "tisb_other",
    12: "mode_ac",
}


@dataclass(frozen=True)
class Aircraft:
    hex: str
    flight: str
    registration: str
    type_code: str
    lat: float
    lon: float
    alt_baro_ft: int | None
    ground_speed_kts: float
    track_deg: float
    squawk: str
    seen_pos_s: float
    seen_s: float
    rssi_db: float
    addr_type: str
    category: str | None
    on_ground: bool


def _read_c_string(data: bytes, start: int, end: int) -> str:
    chars: list[str] = []
    for index in range(start, end):
        if data[index] == 0:
            break
        byte = data[index]
        if 32 < byte < 127:
            chars.append(chr(byte))
    return "".join(chars).strip()


def decode_bincraft(data: bytes, zstd_compressed: bool = True) -> list[Aircraft]:
    if zstd_compressed:
        data = zstandard.ZstdDecompressor().decompress(data)

    if len(data) < 24:
        return []

    stride = struct.unpack_from("<I", data, 8)[0]
    if stride < 108 or stride > 256 or stride > len(data):
        return []

    aircraft: list[Aircraft] = []
    for offset in range(stride, len(data), stride):
        if offset + stride > len(data):
            break

        record = data[offset : offset + stride]
        s32 = struct.unpack_from("<iiii", record, 0)
        u16 = [value[0] for value in struct.iter_unpack("<H", record)]
        s16 = [value[0] for value in struct.iter_unpack("<h", record)]

        lon = s32[2] / 1_000_000
        lat = s32[3] / 1_000_000
        if lat == 0 and lon == 0:
            continue

        airground = record[68] & 0x0F
        on_ground = airground == 1
        baro_alt_valid = bool(record[73] & 0x10)
        baro_alt = s16[10] * 25
        alt_baro_ft = baro_alt if baro_alt_valid and not on_ground else None

        addr_type_id = (record[67] & 0xF0) >> 4
        rssi_raw = record[86] if len(record) > 86 else 0
        rssi_db = 10 * math.log10((rssi_raw * rssi_raw) / 65025 + 1.125e-5)

        aircraft.append(
            Aircraft(
                hex=f"{s32[0] & 0xFFFFFF:06x}",
                flight=_read_c_string(record, 78, 87),
                registration=_read_c_string(record, 92, 104),
                type_code=_read_c_string(record, 88, 92),
                lat=lat,
                lon=lon,
                alt_baro_ft=alt_baro_ft,
                ground_speed_kts=s16[17] / 10,
                track_deg=s16[20] / 90,
                squawk=f"{u16[16]:04x}",
                seen_pos_s=u16[2] / 10,
                seen_s=u16[3] / 10,
                rssi_db=rssi_db,
                addr_type=ADDRTYPE_NAMES.get(addr_type_id, "unknown"),
                category=f"{record[64]:02X}" if record[64] else None,
                on_ground=on_ground,
            )
        )

    return aircraft
