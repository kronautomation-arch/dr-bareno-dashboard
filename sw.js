// Subir la versión en cada cambio de index.html: el fetch handler sirve el HTML
// desde caché primero, así que sin bump los clientes instalados (PWA en iPhone)
// se quedan con el JS viejo aunque data.json sí se actualice.
const CACHE = 'drbareno-v2';
const STATIC = ['/', '/index.html', '/manifest.json'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  // data.json: siempre desde red (datos frescos), fallback a caché
  if (e.request.url.includes('data.json')) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request))
    );
    return;
  }
  // Resto: caché primero
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});
