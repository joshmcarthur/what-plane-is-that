# what plane for Garmin

Connect IQ watch app that looks up the nearest aircraft from the watch GPS, using the same `GET /nearest/at` endpoint as the PWA.

## Settings

After install, open the app's Connect IQ settings (Garmin Connect Mobile or Garmin Express) and set **Server URL** to the HTTPS origin of your what-plane service, with no trailing path:

```text
https://what-plane.example.com
```

The watch needs a phone connection or watch Wi-Fi, and the URL must be reachable from the phone. Garmin's web proxy typically requires HTTPS.

## Build and sideload

1. Install the [Connect IQ SDK](https://developer.garmin.com/connect-iq/sdk/) and the VS Code **Monkey C** extension.
2. Open the `garmin/` folder as the project root, or add `garmin/monkey.jungle` as the jungle file.
3. Run **Monkey C: Generate a Developer Key** if you do not already have one.
4. Pick your watch with **Monkey C: Edit Products** if it is not already listed in `manifest.xml`.
5. Sideload with **Monkey C: Build Project** / **Run**, or:

```bash
monkeyc -f monkey.jungle -d <device_id> -o bin/what-plane.prg -y /path/to/developer_key.der
monkeydo bin/what-plane.prg <device_id>
```

Copy the `.prg` to `GARMIN/APPS` on the watch to sideload without the simulator.

## Usage

Opening the app requests a GPS fix, then `GET /nearest/at?lat=…&lng=…`. On success it shows:

- callsign or registration
- airline and city pair when the API includes a route
- aircraft type
- altitude
- distance and direction

Press **Start** or tap the screen to scan again.
