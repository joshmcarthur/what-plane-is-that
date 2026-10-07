"""Sanity checks for the Connect IQ project (no Monkey C compiler required)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

GARMIN_DIR = Path(__file__).resolve().parents[1] / "garmin"
IQ_NS = {"iq": "http://www.garmin.com/xml/connectiq"}


def test_connect_iq_manifest_is_watch_app_with_gps_and_http() -> None:
    root = ET.parse(GARMIN_DIR / "manifest.xml").getroot()
    application = root.find("iq:application", IQ_NS)
    assert application is not None
    assert application.attrib["type"] == "watch-app"
    assert application.attrib["entry"] == "WhatPlaneApp"

    permissions = [
        node.attrib["id"]
        for node in application.findall("iq:permissions/iq:uses-permission", IQ_NS)
    ]
    assert "Communications" in permissions
    assert "Positioning" in permissions

    products = application.findall("iq:products/iq:product", IQ_NS)
    assert len(products) > 10


def test_connect_iq_settings_expose_server_url() -> None:
    properties = ET.parse(GARMIN_DIR / "resources/settings/properties.xml").getroot()
    ids = [node.attrib["id"] for node in properties.findall("property")]
    assert "baseUrl" in ids

    settings = ET.parse(GARMIN_DIR / "resources/settings/settings.xml").getroot()
    keys = [node.attrib["propertyKey"] for node in settings.findall("setting")]
    assert "@Properties.baseUrl" in keys


def test_connect_iq_sources_call_existing_nearest_at() -> None:
    sources = (GARMIN_DIR / "source").glob("*.mc")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    assert "/nearest/at" in combined
    assert "compact" not in combined
    assert "Communications.makeWebRequest" in combined
    assert "Position.enableLocationEvents" in combined


def test_connect_iq_launcher_icon_is_png() -> None:
    icon = GARMIN_DIR / "resources/drawables/launcher_icon.png"
    assert icon.is_file()
    assert icon.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_jungle_points_at_manifest() -> None:
    jungle = (GARMIN_DIR / "monkey.jungle").read_text(encoding="utf-8")
    assert "project.manifest = manifest.xml" in jungle
