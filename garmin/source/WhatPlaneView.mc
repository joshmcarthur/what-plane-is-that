using Toybox.Graphics;
using Toybox.Lang;
using Toybox.WatchUi;

class WhatPlaneView extends WatchUi.View {
    var lookup;

    function initialize(lookupService) {
        View.initialize();
        lookup = lookupService;
    }

    function onShow() {
        if (lookup.state == :idle) {
            lookup.start();
        }
    }

    function onUpdate(dc) {
        var width = dc.getWidth();
        var height = dc.getHeight();
        var cx = width / 2;
        var margin = width / 8;
        var maxWidth = width - (margin * 2);

        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
        dc.clear();

        if (lookup.state == :result && lookup.data != null) {
            drawResult(dc, cx, height, maxWidth);
            return;
        }

        var statusColor = Graphics.COLOR_LT_GRAY;
        if (lookup.state == :error) {
            statusColor = Graphics.COLOR_RED;
        } else if (lookup.isBusy()) {
            statusColor = Graphics.COLOR_YELLOW;
        }

        dc.setColor(statusColor, Graphics.COLOR_TRANSPARENT);
        drawCentered(dc, lookup.message, Graphics.FONT_SMALL, cx, height / 2, maxWidth);

        dc.setColor(Graphics.COLOR_DK_GRAY, Graphics.COLOR_TRANSPARENT);
        dc.drawText(
            cx,
            height - (height / 8),
            Graphics.FONT_XTINY,
            hintText(),
            Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER
        );
    }

    function drawResult(dc, cx, height, maxWidth) {
        var payload = lookup.data;
        var y = height / 6;
        var gap = 4;

        dc.setColor(Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
        y = drawLine(dc, "Nearest", Graphics.FONT_XTINY, cx, y, maxWidth) + gap;

        dc.setColor(Graphics.COLOR_YELLOW, Graphics.COLOR_TRANSPARENT);
        y = drawLine(dc, headline(payload), Graphics.FONT_MEDIUM, cx, y, maxWidth) + gap;

        var route = dictGet(payload, "route");
        var airline = asString(dictGet(route, "airline"));
        if (airline.length() > 0) {
            dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
            y = drawLine(dc, airline, Graphics.FONT_TINY, cx, y, maxWidth) + 2;
        }

        var cityLine = routeLine(route);
        if (cityLine.length() > 0) {
            dc.setColor(Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
            y = drawLine(dc, cityLine, Graphics.FONT_TINY, cx, y, maxWidth) + gap;
        }

        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        y = drawLine(dc, aircraftType(payload), Graphics.FONT_SMALL, cx, y, maxWidth) + 2;
        y = drawLine(dc, altitudeText(payload), Graphics.FONT_SMALL, cx, y, maxWidth) + 2;
        drawLine(dc, distanceText(payload), Graphics.FONT_SMALL, cx, y, maxWidth);

        dc.setColor(Graphics.COLOR_DK_GRAY, Graphics.COLOR_TRANSPARENT);
        dc.drawText(
            cx,
            height - (height / 8),
            Graphics.FONT_XTINY,
            "Start to refresh",
            Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER
        );
    }

    function hintText() {
        if (lookup.state == :error || lookup.state == :empty) {
            return "Start to retry";
        }
        return "Start to scan";
    }

    function headline(payload) {
        var flight = asString(dictGet(payload, "flight"));
        if (flight.length() > 0) {
            return flight;
        }
        var registration = asString(dictGet(payload, "registration"));
        if (registration.length() > 0) {
            return registration;
        }
        return "Aircraft";
    }

    function aircraftType(payload) {
        var name = asString(dictGet(payload, "type_name"));
        if (name.length() > 0) {
            return name;
        }
        return asString(dictGet(payload, "type"));
    }

    function altitudeText(payload) {
        var altitude = dictGet(payload, "altitude_ft");
        if (altitude == null) {
            return "Unknown altitude";
        }
        return toWhole(altitude).toString() + " ft";
    }

    function distanceText(payload) {
        var km = dictGet(payload, "distance_km");
        var direction = asString(dictGet(payload, "direction"));
        var distance = "Nearby";
        if (km != null) {
            distance = formatKm(km) + " km";
        }
        if (direction.length() > 0) {
            return distance + " " + direction;
        }
        return distance;
    }

    function routeLine(route) {
        var origin = firstString(route, ["origin_municipality", "origin_iata", "origin_icao"]);
        var destination = firstString(route, ["destination_municipality", "destination_iata", "destination_icao"]);
        if (origin.length() == 0 || destination.length() == 0) {
            return "";
        }
        return origin + " -> " + destination;
    }

    function firstString(data, keys) {
        for (var i = 0; i < keys.size(); i++) {
            var value = asString(dictGet(data, keys[i]));
            if (value.length() > 0) {
                return value;
            }
        }
        return "";
    }

    function dictGet(data, key) {
        if (data == null || !(data instanceof Lang.Dictionary)) {
            return null;
        }
        return data.get(key);
    }

    function asString(value) {
        if (value == null) {
            return "";
        }
        return value.toString();
    }

    function toWhole(value) {
        if (value instanceof Lang.Float || value instanceof Lang.Double) {
            return value.toNumber();
        }
        return value;
    }

    function formatKm(value) {
        if (value instanceof Lang.Float || value instanceof Lang.Double) {
            return value.format("%.1f");
        }
        return value.toString();
    }

    function drawLine(dc, text, font, cx, y, maxWidth) {
        if (text == null || text.length() == 0) {
            return y;
        }
        var fitted = fitText(dc, text, font, maxWidth);
        dc.drawText(cx, y, font, fitted, Graphics.TEXT_JUSTIFY_CENTER);
        return y + dc.getFontHeight(font);
    }

    function drawCentered(dc, text, font, cx, cy, maxWidth) {
        var fitted = fitText(dc, asString(text), font, maxWidth);
        dc.drawText(
            cx,
            cy,
            font,
            fitted,
            Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER
        );
    }

    function fitText(dc, text, font, maxWidth) {
        if (dc.getTextWidthInPixels(text, font) <= maxWidth) {
            return text;
        }
        var trimmed = text;
        while (trimmed.length() > 1 && dc.getTextWidthInPixels(trimmed + "...", font) > maxWidth) {
            trimmed = trimmed.substring(0, trimmed.length() - 1);
        }
        return trimmed + "...";
    }
}
