import Toybox.Lang;
import Toybox.WatchUi;

class WhatPlaneDelegate extends WatchUi.BehaviorDelegate {
    var lookup as Lookup;

    function initialize(lookupService as Lookup) {
        BehaviorDelegate.initialize();
        lookup = lookupService;
    }

    function onSelect() as Boolean {
        lookup.start();
        return true;
    }

    function onBack() as Boolean {
        lookup.stop();
        return false;
    }
}
