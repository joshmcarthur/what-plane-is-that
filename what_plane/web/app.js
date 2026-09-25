const $ = (id) => document.getElementById(id);
const status = $("status");
const result = $("result");
const summary = $("summary");
const details = $("details");
const compass = $("compass");
const needle = $("needle");
const locBar = $("loc");
const gsBar = $("gs");
const bearing = $("bearing");
const locate = $("locate");
const refresh = $("refresh");
const compassBtn = $("compass-btn");

const CDI_OFFSET_REM = 3.4;

let current = null;
let orientation = null;
let pointingOn = false;
let observerAltM = 0;

function setStatus(text, kind) {
  status.textContent = text;
  status.className = "status" + (kind ? ` ${kind}` : "");
}

function show(el, visible) {
  el.classList.toggle("hidden", !visible);
}

function detail(label, value) {
  const wrap = document.createElement("div");
  wrap.innerHTML = `<dt>${label}</dt><dd>${value}</dd>`;
  return wrap;
}

function sensorsReady() {
  return (
    pointingOn &&
    orientation != null &&
    orientation.heading != null &&
    orientation.alpha != null &&
    orientation.beta != null &&
    orientation.gamma != null
  );
}

function currentElevationDeg() {
  if (current?.altitude_ft == null) return 0;
  if (observerAltM) {
    return Pointer.elevationDeg(current.distance_km, current.altitude_ft, observerAltM);
  }
  if (current.elevation_deg != null) return current.elevation_deg;
  return Pointer.elevationDeg(current.distance_km, current.altitude_ft);
}

function updateCompass() {
  if (!current?.found || current.bearing_deg == null) {
    show(bearing, false);
    return;
  }

  const ready = sensorsReady();
  compass.classList.toggle("fallback", !ready);

  if (!ready) {
    compass.classList.remove("locked");
    needle.style.transform = `rotate(${current.bearing_deg}deg)`;
    bearing.textContent = `Bearing ${Math.round(current.bearing_deg)}° ${current.direction}`;
    show(bearing, true);
    return;
  }

  const deviation = Pointer.cdiDeviations({
    alpha: orientation.alpha,
    beta: orientation.beta,
    gamma: orientation.gamma,
    headingDeg: orientation.heading,
    bearingDeg: current.bearing_deg,
    elevationDeg: currentElevationDeg(),
  });
  const scale = CDI_OFFSET_REM / Pointer.FULL_SCALE_DEG;
  locBar.style.transform = `translateX(${deviation.loc * scale}rem)`;
  gsBar.style.transform = `translateY(${-deviation.gs * scale}rem)`;
  compass.classList.toggle("locked", deviation.locked);
  bearing.textContent = Pointer.cdiCaption(deviation);
  show(bearing, true);
}

function render(data) {
  current = data;
  show(result, true);
  summary.textContent = data.summary || "No aircraft found.";
  details.replaceChildren();
  if (data.found) {
    const type = data.type_name || data.type || "Unknown";
    const alt = data.altitude_ft == null ? "Unknown" : `${data.altitude_ft.toLocaleString()} ft`;
    details.append(
      detail("Type", type),
      detail("Altitude", alt),
      detail("Distance", data.distance_text || `${data.distance_km} km`),
      detail("Direction", data.direction || "—"),
    );
  }
  show(refresh, true);
  show(compassBtn, data.found && !pointingOn);
  updateCompass();
}

async function fetchNearest(lat, lng) {
  const res = await fetch(`/nearest/at?lat=${lat}&lng=${lng}`);
  if (!res.ok) throw new Error(`Lookup failed (${res.status})`);
  return res.json();
}

function getPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Geolocation not supported."));
      return;
    }
    navigator.geolocation.getCurrentPosition(resolve, (err) => {
      const msg = { 1: "Location denied.", 2: "Location unavailable.", 3: "Location timed out." };
      reject(new Error(msg[err.code] || "Location failed."));
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 });
  });
}

async function runLookup() {
  locate.disabled = refresh.disabled = true;
  setStatus("Getting location…", "loading");
  try {
    const pos = await getPosition();
    const { latitude: lat, longitude: lng, altitude } = pos.coords;
    observerAltM = Number.isFinite(altitude) ? altitude : 0;
    setStatus("Scanning nearby…", "loading");
    const data = await fetchNearest(lat, lng);
    render(data);
    setStatus(data.found ? "Updated." : "No aircraft in range.");
  } catch (err) {
    show(result, false);
    show(refresh, false);
    show(compassBtn, false);
    setStatus(err.message, "error");
  } finally {
    locate.disabled = refresh.disabled = false;
  }
}

function readOrientation(event) {
  const beta = event.beta;
  const gamma = event.gamma;
  let heading = null;
  let alpha = event.alpha;
  if (event.webkitCompassHeading != null) {
    heading = event.webkitCompassHeading;
    alpha = (360 - event.webkitCompassHeading) % 360;
  } else if (event.alpha != null) {
    heading = (360 - event.alpha + 360) % 360;
  }
  if (heading == null || alpha == null || beta == null || gamma == null) return null;
  return { alpha, beta, gamma, heading };
}

let haveAbsolute = false;

function onOrientation(event) {
  if (event.type === "deviceorientationabsolute") haveAbsolute = true;
  if (event.type === "deviceorientation" && haveAbsolute && event.webkitCompassHeading == null) {
    return;
  }
  const value = readOrientation(event);
  if (value != null) {
    orientation = value;
    updateCompass();
  }
}

async function enablePointing() {
  const ctor = window.DeviceOrientationEvent;
  if (!ctor) return;

  if (typeof ctor.requestPermission === "function") {
    const ok = await ctor.requestPermission().catch(() => "denied");
    if (ok !== "granted") return;
  }

  pointingOn = true;
  window.addEventListener("deviceorientationabsolute", onOrientation, true);
  window.addEventListener("deviceorientation", onOrientation, true);
  show(compassBtn, false);
  updateCompass();
}

locate.addEventListener("click", () => void runLookup());
refresh.addEventListener("click", () => void runLookup());
compassBtn.addEventListener("click", () => void enablePointing());

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

if (!navigator.onLine) {
  setStatus("Offline — lookups need a network.", "error");
}
