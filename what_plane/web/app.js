const $ = (id) => document.getElementById(id);
const status = $("status");
const result = $("result");
const summary = $("summary");
const details = $("details");
const compass = $("compass");
const needle = $("needle");
const bearing = $("bearing");
const locate = $("locate");
const refresh = $("refresh");
const compassBtn = $("compass-btn");

let current = null;
let heading = null;
let compassOn = false;

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

function updateCompass() {
  if (!current?.found || current.bearing_deg == null) {
    show(bearing, false);
    return;
  }

  const deg = current.bearing_deg;
  const rel = compassOn && heading != null ? deg - heading : deg;
  needle.style.transform = `rotate(${rel}deg)`;
  compass.classList.toggle("fallback", !compassOn || heading == null);
  bearing.textContent = compassOn && heading != null
    ? `Point toward ${current.direction}`
    : `Bearing ${Math.round(deg)}° ${current.direction}`;
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
  show(compassBtn, data.found && !compassOn);
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
    const { latitude: lat, longitude: lng } = pos.coords;
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

function readHeading(event) {
  if (event.webkitCompassHeading != null) return event.webkitCompassHeading;
  if (event.alpha != null) return 360 - event.alpha;
  return null;
}

function onOrientation(event) {
  const value = readHeading(event);
  if (value != null) {
    heading = value;
    updateCompass();
  }
}

async function enableCompass() {
  const ctor = window.DeviceOrientationEvent;
  if (!ctor) return;

  if (typeof ctor.requestPermission === "function") {
    const ok = await ctor.requestPermission().catch(() => "denied");
    if (ok !== "granted") return;
  }

  compassOn = true;
  window.addEventListener("deviceorientationabsolute", onOrientation, true);
  window.addEventListener("deviceorientation", onOrientation, true);
  show(compassBtn, false);
  updateCompass();
}

locate.addEventListener("click", () => void runLookup());
refresh.addEventListener("click", () => void runLookup());
compassBtn.addEventListener("click", () => void enableCompass());

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

if (!navigator.onLine) {
  setStatus("Offline — lookups need a network.", "error");
}
