document.addEventListener('DOMContentLoaded', () => {
  // Favicon — shield SVG (matches landing page)
  const shieldFavicon = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36" fill="none"%3E%3Cpath d="M18 3L4 9v6c0 7.5 5 12.5 14 14.5 9-2 14-7 14-14.5V9L18 3z" fill="%23a855f7" opacity="0.15"/%3E%3Cpath d="M18 3L4 9v6c0 7.5 5 12.5 14 14.5 9-2 14-7 14-14.5V9L18 3z" stroke="%23a855f7" stroke-width="2" stroke-linejoin="round"/%3E%3Cpath d="M13 18l4 4 10-10" stroke="%23a855f7" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/%3E%3C/svg%3E';

  const link = document.createElement('link');
  link.rel = 'icon';
  link.type = 'image/svg+xml';
  link.href = shieldFavicon;
  document.head.appendChild(link);

  // ── API test buttons ──────────────────────────────────────────
  const apiUrls = {
    'api-check':   '/api/',
    'db-check':    '/api/db-check',
    'db-items':    '/api/db-items',
  };

  function prettyJson(obj) {
    return JSON.stringify(obj, null, 2);
  }

  function fetchApi(btnId, url) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      btn.textContent = 'Loading…';
      try {
        const resp = await fetch(url);
        if (!resp.ok) {
          btn.textContent = `Error ${resp.status}`;
          return;
        }
        const data = await resp.json();
        // Show result in a simple alert for now — could also inject
        // into the page; alert keeps it lightweight and matches the
        // "click to see raw JSON" description on the page.
        alert(prettyJson(data));
      } catch (err) {
        btn.textContent = 'Failed';
        console.error('API fetch error:', err);
      } finally {
        btn.disabled = false;
        // Restore original label
        const labels = {
          'api-check': 'GET /api/',
          'db-check':  'GET /api/db-check',
          'db-items':  'GET /api/db-items',
        };
        btn.textContent = labels[btnId] || 'Try API';
      }
    });
  }

  for (const [btnId, url] of Object.entries(apiUrls)) {
    fetchApi(btnId, url);
  }
});
