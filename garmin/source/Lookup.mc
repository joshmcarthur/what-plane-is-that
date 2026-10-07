import Toybox.Application;
import Toybox.Communications;
import Toybox.Lang;
import Toybox.Position;
import Toybox.Timer;
import Toybox.WatchUi;

class Lookup {
    var state as Symbol = :idle;
    var data as Dictionary?;
    var message as String = "Press start to scan";
    var timer as Timer.Timer?;
    var lastInfo as Position.Info?;

    function initialize() {
        data = null;
        timer = null;
        lastInfo = null;
    }

    function isBusy() as Boolean {
        return state == :locating || state == :scanning;
    }

    function start() as Void {
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

    function stop() as Void {
        cancelTimer();
        Position.enableLocationEvents(Position.LOCATION_DISABLE, null);
        if (state == :locating || state == :scanning) {
            state = :idle;
            message = "Press start to scan";
            refresh();
        }
    }

    function onPosition(info as Position.Info) as Void {
        if (state != :locating) {
            return;
        }
        lastInfo = info;
        if (info.position == null || info.accuracy == null) {
            return;
        }
        if (info.accuracy >= Position.QUALITY_USABLE) {
            fetchNearest(info);
        }
    }

    function onTimeout() as Void {
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

    function onResponse(responseCode as Number, payload as Dictionary or String or Null) as Void {
        cancelTimer();
        if (state != :scanning) {
            return;
        }

        if (responseCode != 200 || !(payload instanceof Dictionary)) {
            fail(errorMessage(responseCode));
            return;
        }

        var body = payload as Dictionary;
        data = body;
        if (body.get("found") == true) {
            state = :result;
            message = "";
        } else {
            state = :empty;
            message = "No aircraft nearby";
        }
        refresh();
    }

    function fetchNearest(info as Position.Info) as Void {
        cancelTimer();
        Position.enableLocationEvents(Position.LOCATION_DISABLE, null);

        var loc = info.position;
        if (loc == null) {
            fail("Location unavailable");
            return;
        }

        var degrees = loc.toDegrees() as Array<Double>;
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

    function serverUrl() as String? {
        var raw = Application.Properties.getValue("baseUrl");
        var url = raw == null ? "" : raw.toString();
        while (url.length() > 0 && url.substring(url.length() - 1, url.length()).equals("/")) {
            url = url.substring(0, url.length() - 1);
        }
        if (url.length() == 0) {
            return null;
        }
        return url;
    }

    function errorMessage(code as Number) as String {
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
        if (code == 0) {
            return "Lookup failed";
        }
        return "Lookup failed (" + code.toString() + ")";
    }

    function fail(text as String) as Void {
        cancelTimer();
        Position.enableLocationEvents(Position.LOCATION_DISABLE, null);
        state = :error;
        data = null;
        message = text;
        refresh();
    }

    function startTimer(ms as Number) as Void {
        cancelTimer();
        timer = new Timer.Timer();
        timer.start(method(:onTimeout), ms, false);
    }

    function cancelTimer() as Void {
        if (timer != null) {
            timer.stop();
            timer = null;
        }
    }

    function refresh() as Void {
        WatchUi.requestUpdate();
    }
}
