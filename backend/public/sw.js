const CACHE_NAME = 'vli-dashboard-cache-v41';
const URLS_TO_CACHE = [
  '/vli_dashboard.html'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(URLS_TO_CACHE))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  // Do not cache API requests
  if (event.request.url.includes('/api/')) {
    return;
  }
  
  // For the dashboard HTML, try network first, then fallback to cache
  if (event.request.url.includes('vli_dashboard.html')) {
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match('/vli_dashboard.html', { ignoreSearch: true }).then(response => {
          return response || new Response('<html><body style="background:#000;color:#fff;text-align:center;padding:50px;">Dashboard Offline. Cache miss.</body></html>', { headers: { 'Content-Type': 'text/html' }});
        });
      })
    );
    return;
  }
  
  // For all other requests, try cache first, then network
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        return response || fetch(event.request);
      })
      .catch(() => {
        // Fallback for offline if it's the root or dashboard
        if (event.request.mode === 'navigate') {
          return caches.match('/vli_dashboard.html', { ignoreSearch: true }).then(response => {
            return response || new Response('<html><body style="background:#000;color:#fff;text-align:center;padding:50px;">Dashboard Offline. Cache miss.</body></html>', { headers: { 'Content-Type': 'text/html' }});
          });
        }
      })
  );
});
