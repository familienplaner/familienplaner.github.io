/* Familienboard – minimaler Service Worker: macht die Seite als App installierbar.
   Kein Zwischenspeichern, damit Updates sofort ankommen. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
