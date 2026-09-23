"""Tests for the on-the-go PWA static assets."""

from __future__ import annotations

import pytest
import what_plane.main as main_module
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    return TestClient(main_module.app)


def test_web_index(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "what plane" in response.text.lower()


def test_manifest(client: TestClient) -> None:
    response = client.get("/manifest.webmanifest")

    assert response.status_code == 200
    assert "application/manifest+json" in response.headers["content-type"]
