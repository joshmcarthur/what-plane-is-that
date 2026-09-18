"""Fetch and decode aircraft snapshots from ADS-B Exchange."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import httpx
from what_plane.bincraft import Aircraft, decode_bincraft
from what_plane.geo import BoundingBox

DEFAULT_API_URL = "https://globe.adsbexchange.com/re-api/"
DEFAULT_REFERER = "https://globe.adsbexchange.com/"


@dataclass
class FetchResult:
    aircraft: list[Aircraft]
    fetched_at: float
    source_url: str


class AdsbExchangeClient:
    def __init__(
        self,
        api_url: str | None = None,
        referer: str | None = None,
        timeout_s: float = 15.0,
    ) -> None:
        self.api_url = api_url or os.getenv("ADSBEXCHANGE_API_URL", DEFAULT_API_URL)
        self.referer = referer or os.getenv("ADSBEXCHANGE_REFERER", DEFAULT_REFERER)
        self.timeout_s = timeout_s

    async def fetch_box(self, box: BoundingBox) -> FetchResult:
        # ADS-B Exchange expects flag-style params (?binCraft&zstd&box=...).
        url = f"{self.api_url}?binCraft&zstd&box={box.as_api_param()}"
        headers = {
            "accept": "*/*",
            "referer": self.referer,
        }

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

        aircraft = decode_bincraft(response.content, zstd_compressed=True)
        return FetchResult(
            aircraft=aircraft,
            fetched_at=time.time(),
            source_url=str(response.request.url),
        )
