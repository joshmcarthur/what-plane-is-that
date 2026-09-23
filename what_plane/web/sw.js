const CACHE = "what-plane-v1";
const SHELL = ["/", "/styles.css", "/app.js", "/manifest.webmanifest", "/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("fetch", (event) => {
  const path = new URL(event.request.url).pathname;
  if (event.request.method !== "GET" || path.startsWith("/nearest") || path.startsWith("/health")) {
    return;
  }
  event.respondWith(caches.match(event.request).then((hit) => hit || fetch(event.request)));
});
