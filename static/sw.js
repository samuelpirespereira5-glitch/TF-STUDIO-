const CACHE = 'jarvis-static-v2';
const ASSETS = [
  '/static/css/style.css',
  '/static/css/jarvis-world.css',
  '/static/js/jarvis-world.js'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.pathname.startsWith('/api/')) return;

  // Network-first for HTML/pages so CSP/script updates apply immediately
  const isDoc =
    e.request.mode === 'navigate' ||
    (e.request.headers.get('accept') || '').includes('text/html') ||
    u.pathname.endsWith('.html') ||
    !u.pathname.startsWith('/static/');

  if (isDoc) {
    e.respondWith(
      fetch(e.request)
        .then((r) => r)
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // Cache-first for static assets
  e.respondWith(
    caches.match(e.request).then((c) => {
      if (c) return c;
      return fetch(e.request).then((r) => {
        const copy = r.clone();
        caches.open(CACHE).then((x) => x.put(e.request, copy));
        return r;
      }).catch(() => c);
    })
  );
});
