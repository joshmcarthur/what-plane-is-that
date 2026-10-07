import Toybox.Application;
import Toybox.Communications;
import Toybox.Graphics;
import Toybox.Lang;
import Toybox.Position;
import Toybox.Timer;
import Toybox.WatchUi;

class WhatPlaneApp extends Application.AppBase {
    var view as WhatPlaneView?;

    function initialize() {
        AppBase.initialize();
    }

    function onStop(state as Dictionary?) as Void {
        if (view != null) {
            view.stop();
        }
    }

    function getInitialView() as [Views] or [Views, InputDelegates] {
        view = new WhatPlaneView();
        return [view, new WhatPlaneDelegate(view)];
    }
}

class WhatPlaneDelegate extends WatchUi.BehaviorDelegate {
    var view as WhatPlaneView;

    function initialize(planeView as WhatPlaneView) {
        BehaviorDelegate.initialize();
        view = planeView;
    }

    function onSelect() as Boolean {
        view.start();
        return true;
    }
}

class WhatPlaneView extends WatchUi.View {
    var plane as Dictionary?;
    var message as String = "Getting location";
    var busy as Boolean = false;
    var timer as Timer.Timer?;

    function initialize() {
        View.initialize();
        plane = null;
        timer = null;
    }

    function onShow() as Void {
        if (!busy && plane == null) {
            start();
        }
    }

    function onUpdate(dc as Dc) as Void {
        var cx = dc.getWidth() / 2;
        var y = dc.getHeight() / 6;

        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
        dc.clear();

        if (plane != null) {
            var title = field(plane, "flight");
            if (title.length() == 0) {
                title = field(plane, "registration");
            }
            var kind = field(plane, "type_name");
            if (kind.length() == 0) {
                kind = field(plane, "type");
            }
            var altitude = field(plane, "altitude_ft");
            var distance = field(plane, "distance_text");
            if (distance.length() == 0) {
                distance = field(plane, "distance_km");
            }
            var direction = field(plane, "direction");
            if (direction.length() > 0) {
                distance = distance.length() > 0 ? distance + " " + direction : direction;
            }
            y = line(dc, title, Graphics.FONT_MEDIUM, cx, y);
            y = line(dc, kind, Graphics.FONT_SMALL, cx, y);
            if (altitude.length() > 0) {
                y = line(dc, altitude + " ft", Graphics.FONT_SMALL, cx, y);
            }
            line(dc, distance, Graphics.FONT_SMALL, cx, y);
            return;
        }

        dc.drawText(
            cx,
            dc.getHeight() / 2,
            Graphics.FONT_SMALL,
            message,
            Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER
        );
    }

    function start() as Void {
        if (busy) {
            return;
        }

        var raw = Application.Properties.getValue("baseUrl");
        if (raw == null || raw.toString().length() == 0) {
            plane = null;
            message = "Set server URL in Connect IQ settings";
            WatchUi.requestUpdate();
            return;
        }

        busy = true;
        plane = null;
        message = "Getting location";
        WatchUi.requestUpdate();
        Position.enableLocationEvents(Position.LOCATION_CONTINUOUS, method(:onPosition));
        timer = new Timer.Timer();
        timer.start(method(:onTimeout), 25000, false);
    }

    function stop() as Void {
        if (timer != null) {
            timer.stop();
            timer = null;
        }
        Position.enableLocationEvents(Position.LOCATION_DISABLE, null);
        busy = false;
    }

    function onTimeout() as Void {
        timer = null;
        if (busy) {
            fail("Location unavailable");
        }
    }

    function onPosition(info as Position.Info) as Void {
        if (!busy || timer == null || info.position == null) {
            return;
        }

        var loc = info.position as Position.Location;
        var degrees = loc.toDegrees() as Array<Double>;
        timer.stop();
        timer = null;
        Position.enableLocationEvents(Position.LOCATION_DISABLE, null);

        message = "Scanning nearby";
        WatchUi.requestUpdate();

        var url = Application.Properties.getValue("baseUrl").toString() + "/nearest/at";
        Communications.makeWebRequest(
            url,
            {"lat" => degrees[0].toString(), "lng" => degrees[1].toString()},
            {
                :method => Communications.HTTP_REQUEST_METHOD_GET,
                :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
            },
            method(:onResponse)
        );
    }

    function onResponse(code as Number, data as Dictionary or String or Null) as Void {
        busy = false;
        if (code != 200 || !(data instanceof Dictionary)) {
            fail(code == -104 ? "Phone not connected" : "Lookup failed");
            return;
        }

        var body = data as Dictionary;
        if (body.get("found") == true) {
            plane = body;
            message = "";
        } else {
            plane = null;
            message = "No aircraft nearby";
        }
        WatchUi.requestUpdate();
    }

    function fail(text as String) as Void {
        stop();
        plane = null;
        message = text;
        WatchUi.requestUpdate();
    }

    function field(data as Dictionary, key as String) as String {
        var value = data.get(key);
        return value == null ? "" : value.toString();
    }

    function line(dc as Dc, text as String, font as FontDefinition, cx as Number, y as Number) as Number {
        if (text.length() == 0) {
            return y;
        }
        dc.drawText(cx, y, font, text, Graphics.TEXT_JUSTIFY_CENTER);
        return y + dc.getFontHeight(font) + 2;
    }
}
