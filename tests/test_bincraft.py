"""Tests for binCraft decoding."""

from __future__ import annotations

from what_plane.bincraft import decode_bincraft


def test_decode_bincraft_rejects_short_payload() -> None:
    assert decode_bincraft(b"short", zstd_compressed=False) == []


def test_decode_bincraft_rejects_invalid_stride() -> None:
    payload = b"\x00" * 8 + b"\xff\x00\x00\x00" + b"\x00" * 20
    assert decode_bincraft(payload, zstd_compressed=False) == []
