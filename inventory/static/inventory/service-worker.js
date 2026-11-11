const CACHE_NAME = 'wled-inv-v1';
const ASSETS_TO_CACHE = [
  '/parts/',
  '/static/inventory/manifest.json',
  // Add any core CSS or structural JS file paths your dashboard relies on here
];

// Installs the background application lifecycle layer
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
});

// Intercepts smartphone browser traffic to serve cached framework files directly
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      return cachedResponse || fetch(event.request);
    })
  );
});
