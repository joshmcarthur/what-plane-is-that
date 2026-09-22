"""Tests for adsbdb route lookup."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from what_plane.adsbdb import (
    AdsbDbClient,
    Airport,
    normalize_callsign,
    parse_callsign_response,
    route_to_dict,
)

SAMPLE_RESPONSE = {
    "response": {
        "flightroute": {
            "callsign": "ANZ362M",
            "callsign_icao": "ANZ362M",
            "callsign_iata": "NZ362M",
            "airline": {
                "name": "Air New Zealand",
                "icao": "ANZ",
                "iata": "NZ",
            },
            "origin": {
                "iata_code": "CHC",
                "icao_code": "NZCH",
                "municipality": "Christchurch",
                "name": "Christchurch International Airport",
            },
            "destination": {
                "iata_code": "WLG",
                "icao_code": "NZWN",
                "municipality": "Wellington",
                "name": "Wellington International Airport",
            },
        }
    }
}


def test_normalize_callsign_strips_and_uppercases() -> None:
    assert normalize_callsign(" anz362m ") == "ANZ362M"


def test_parse_callsign_response_returns_route() -> None:
    route = parse_callsign_response(SAMPLE_RESPONSE)

    assert route is not None
    assert route.callsign == "ANZ362M"
    assert route.airline == "Air New Zealand"
    assert route.origin == Airport(
        icao="NZCH",
        iata="CHC",
        name="Christchurch International Airport",
        municipality="Christchurch",
    )
    assert route.destination.icao == "NZWN"


def test_parse_callsign_response_unknown_callsign() -> None:
    assert parse_callsign_response({"response": "unknown callsign"}) is None


def test_route_to_dict() -> None:
    route = parse_callsign_response(SAMPLE_RESPONSE)
    assert route is not None

    payload = route_to_dict(route)

    assert payload["origin_icao"] == "NZCH"
    assert payload["destination_iata"] == "WLG"
    assert payload["airline"] == "Air New Zealand"


@pytest.mark.asyncio
async def test_lookup_route_uses_cache() -> None:
    client = AdsbDbClient(cache_ttl_seconds=60.0)
    mock_response = AsyncMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json = lambda: SAMPLE_RESPONSE

    with patch("what_plane.adsbdb.httpx.AsyncClient") as async_client:
        http_client = AsyncMock()
        http_client.__aenter__.return_value = http_client
        http_client.get.return_value = mock_response
        async_client.return_value = http_client

        first = await client.lookup_route("ANZ362M")
        second = await client.lookup_route("anz362m ")

    assert first is not None
    assert second is not None
    assert second.destination.icao == "NZWN"
    http_client.get.assert_awaited_once()
