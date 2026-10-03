// El HTML y data.json van network-first: con cache-first el iPhone del Dr. se
// quedó con un index.html viejo sin la pestaña Bot vs Asistente (2026-10-03)
// porque nadie subió la versión. Subirla igual limpia cachés viejos.
const CACHE = 'drbareno-v3';
// Relativas: el sitio vive en /dr-bareno-dashboard/, no en la raíz del dominio.
const STATIC = ['./', 'index.html', 'manifest.json'];

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
  // data.json y la página: siempre desde red, fallback a caché sin conexión
  if (e.request.url.includes('data.json') || e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request)
        .then(res => {
          if (e.request.mode === 'navigate' && res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then(c => c.put(e.request, copy));
          }
          return res;
        })
        .catch(() => caches.match(e.request).then(r => r || caches.match('index.html')))
    );
    return;
  }
  // Resto (íconos, manifest): caché primero
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});
