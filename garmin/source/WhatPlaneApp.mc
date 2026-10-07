using Toybox.Application;
using Toybox.WatchUi;

class WhatPlaneApp extends Application.AppBase {
    var lookup;

    function initialize() {
        AppBase.initialize();
        lookup = new Lookup();
    }

    function onStop(state) {
        lookup.stop();
    }

    function getInitialView() {
        return [new WhatPlaneView(lookup), new WhatPlaneDelegate(lookup)];
    }
}
