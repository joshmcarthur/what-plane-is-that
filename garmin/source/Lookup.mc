using Toybox.Application;
using Toybox.Communications;
using Toybox.Lang;
using Toybox.Position;
using Toybox.Timer;
using Toybox.WatchUi;

class Lookup {
    var state = :idle;
    var data = null;
    var message = "Press start to scan";
    var timer = null;
    var lastInfo = null;

    function initialize() {
    }

    function isBusy() {
        return state == :locating || state == :scanning;
    }

    function start() {
        if (isBusy()) {
            return;
        }

        var url = serverUrl();
        if (url == null) {
            fail("Set server URL in Connect IQ settings");
            return;
        }

        state = :locating;
        data = null;
        lastInfo = null;
        message = "Getting location";
        refresh();
        Position.enableLocationEvents(Position.LOCATION_CONTINUOUS, method(:onPosition));
        startTimer(25000);
    }

    function stop() {
        cancelTimer();
        Position.enableLocationEvents(Position.LOCATION_DISABLE, null);
        if (state == :locating || state == :scanning) {
            state = :idle;
            message = "Press start to scan";
            refresh();
        }
    }

    function onPosition(info) {
        if (state != :locating) {
            return;
        }
        lastInfo = info;
        if (info == null || info.position == null || info.accuracy == null) {
            return;
        }
        if (info.accuracy >= Position.QUALITY_USABLE) {
            fetchNearest(info);
        }
    }

    function onTimeout() {
        timer = null;
        if (state == :locating) {
            if (lastInfo != null && lastInfo.position != null) {
                fetchNearest(lastInfo);
            } else {
                Position.enableLocationEvents(Position.LOCATION_DISABLE, null);
                fail("Location unavailable");
            }
        } else if (state == :scanning) {
            fail("Lookup timed out");
        }
    }

    function onResponse(code, payload) {
        cancelTimer();
        if (state != :scanning) {
            return;
        }

        if (code != 200 || payload == null || !(payload instanceof Lang.Dictionary)) {
            fail(errorMessage(code));
            return;
        }

        data = payload;
        var found = payload.get("found");
        if (found == true) {
            state = :result;
            message = "";
        } else {
            state = :empty;
            message = "No aircraft nearby";
        }
        refresh();
    }

    function fetchNearest(info) {
        cancelTimer();
        Position.enableLocationEvents(Position.LOCATION_DISABLE, null);

        var degrees = info.position.toDegrees();
        state = :scanning;
        message = "Scanning nearby";
        refresh();

        var url = serverUrl() + "/nearest/at";
        var params = {
            "lat" => degrees[0].toString(),
            "lng" => degrees[1].toString()
        };
        var options = {
            :method => Communications.HTTP_REQUEST_METHOD_GET,
            :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
        };
        Communications.makeWebRequest(url, params, options, method(:onResponse));
        startTimer(20000);
    }

    function serverUrl() {
        var raw = Application.Properties.getValue("baseUrl");
        if (raw == null) {
            return null;
        }
        var url = raw.toString();
        while (url.length() > 0 && url.substring(url.length() - 1, url.length()).equals("/")) {
            url = url.substring(0, url.length() - 1);
        }
        if (url.length() == 0) {
            return null;
        }
        return url;
    }

    function errorMessage(code) {
        if (code == 502) {
            return "Aircraft feed unavailable";
        }
        if (code == 503) {
            return "Service not configured";
        }
        if (code == -104) {
            return "Phone not connected";
        }
        if (code == -300) {
            return "Request timed out";
        }
        if (code == -400 || code == -403) {
            return "Bad response from server";
        }
        if (code == 0 || code == null) {
            return "Lookup failed";
        }
        return "Lookup failed (" + code.toString() + ")";
    }

    function fail(text) {
        cancelTimer();
        Position.enableLocationEvents(Position.LOCATION_DISABLE, null);
        state = :error;
        data = null;
        message = text;
        refresh();
    }

    function startTimer(ms) {
        cancelTimer();
        timer = new Timer.Timer();
        timer.start(method(:onTimeout), ms, false);
    }

    function cancelTimer() {
        if (timer != null) {
            timer.stop();
            timer = null;
        }
    }

    function refresh() {
        WatchUi.requestUpdate();
    }
}
