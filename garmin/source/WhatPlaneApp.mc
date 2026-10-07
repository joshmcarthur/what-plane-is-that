import Toybox.Application;
import Toybox.Lang;
import Toybox.WatchUi;

class WhatPlaneApp extends Application.AppBase {
    var lookup as Lookup;

    function initialize() {
        AppBase.initialize();
        lookup = new Lookup();
    }

    function onStop(state as Dictionary?) as Void {
        lookup.stop();
    }

    function getInitialView() as [Views] or [Views, InputDelegates] {
        return [new WhatPlaneView(lookup), new WhatPlaneDelegate(lookup)];
    }
}
