/* 离线缓存 Service Worker：首次安装后全部资源本地化 */
const CACHE = 'doorwin-v5';
const ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './css/style.css',
  './lib/three.min.js',
  './lib/OrbitControls.js',
  './lib/qrcode.min.js',
  './js/library.js',
  './js/models.js',
  './js/scene.js',
  './js/drawing.js',
  './js/quote.js',
  './js/export.js',
  './js/main.js',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/apple-touch-icon.png',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE).map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(
    caches.match(e.request).then(hit => {
      const net = fetch(e.request).then(res => {
        // 成功时更新缓存
        if (res && res.status === 200 && e.request.url.indexOf('http') === 0) {
          const copy = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, copy));
        }
        return res;
      }).catch(() => hit);
      return hit || net;
    })
  );
});
