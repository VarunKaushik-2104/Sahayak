
/* Offline shell. The app and syllabus are cached; API requests go to the network. */
const C = 'sahayak-v6';

const SHELL = [
  './',
  'index.html',
  'js/boot.js',
  'js/api.js',
  'js/engine.js',
  'js/app.js',
  'manifest.json'
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(C)
      .then(c => c.addAll(SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== C).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const r = e.request;
  const u = new URL(r.url);

  if (r.method !== 'GET' || u.origin !== location.origin) return;

  if (u.pathname.startsWith('/api/') &&
      u.pathname !== '/api/content/bundle') return;

  e.respondWith(
    (u.pathname === '/app/js/app.js'
      ? fetch(new Request(r, { cache: 'reload' }))
      : fetch(r)
    )
    .then(res => {
      if (res.ok) {
        const cp = res.clone();
        caches.open(C).then(c => c.put(r, cp));
      }
      return res;
    })
    .catch(() =>
      caches.match(r).then(m => m || caches.match('index.html'))
    )
  );
});
