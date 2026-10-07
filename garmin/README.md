# what plane for Garmin

Watch app: GPS → `GET /nearest/at` → callsign, type, altitude, distance.

Set **Server URL** in Connect IQ settings to the HTTPS origin of your what-plane service (`https://what-plane.example.com`). Sideload with the [Connect IQ SDK](https://developer.garmin.com/connect-iq/sdk/):

```bash
monkeyc -f monkey.jungle -d <device_id> -o bin/what-plane.prg -y /path/to/developer_key.der
```

`manifest.xml` lists current Garmin watches (CI compiles `fenix7`). Add a product id only for a device that is missing.
