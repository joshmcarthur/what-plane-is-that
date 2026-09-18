"""Tests for ADS-B Exchange client."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from tests.bincraft_fixtures import build_compressed_bincraft_payload
from what_plane.adsbexchange import AdsbExchangeClient
from what_plane.geo import bounding_box


@pytest.mark.asyncio
async def test_fetch_box_returns_decoded_aircraft() -> None:
    client = AdsbExchangeClient(
        api_url="https://example.test/re-api/",
        referer="https://example.test/",
    )
    box = bounding_box(-41.30, 174.77, 15.0)
    response = AsyncMock()
    response.content = build_compressed_bincraft_payload()
    response.request.url = "https://example.test/re-api/?binCraft&zstd&box=1"
    response.raise_for_status = lambda: None

    mock_http = AsyncMock()
    mock_http.get.return_value = response
    mock_http.__aenter__.return_value = mock_http
    mock_http.__aexit__.return_value = None

    with patch("what_plane.adsbexchange.httpx.AsyncClient", return_value=mock_http):
        result = await client.fetch_box(box)

    assert len(result.aircraft) == 1
    assert result.aircraft[0].flight == "TEST1"
    mock_http.get.assert_awaited_once()
    called_url = mock_http.get.await_args.args[0]
    assert "binCraft&zstd&box=" in called_url
    assert (
        mock_http.get.await_args.kwargs["headers"]["referer"] == "https://example.test/"
    )
