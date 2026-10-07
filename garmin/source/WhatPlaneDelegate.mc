using Toybox.WatchUi;

class WhatPlaneDelegate extends WatchUi.BehaviorDelegate {
    var lookup;

    function initialize(lookupService) {
        BehaviorDelegate.initialize();
        lookup = lookupService;
    }

    function onSelect() {
        lookup.start();
        return true;
    }

    function onBack() {
        lookup.stop();
        return false;
    }
}
