"""Tests for site configuration."""

from __future__ import annotations

import pytest
from what_plane.config import load_observer_config


def test_load_observer_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OBSERVER_LAT", "-41.29")
    monkeypatch.setenv("OBSERVER_LNG", "174.78")
    monkeypatch.setenv("NEAREST_RADIUS_KM", "12")
    monkeypatch.setenv("NEAREST_MAX_ALT_FT", "8000")
    monkeypatch.setenv("NEAREST_MAX_SEEN_POS_S", "15")

    config = load_observer_config()

    assert config.lat == -41.29
    assert config.lng == 174.78
    assert config.radius_km == 12.0
    assert config.max_alt_ft == 8000
    assert config.max_seen_pos_s == 15.0


def test_load_observer_config_requires_coordinates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OBSERVER_LAT", raising=False)
    monkeypatch.delenv("OBSERVER_LNG", raising=False)

    with pytest.raises(ValueError, match="OBSERVER_LAT is required"):
        load_observer_config()
