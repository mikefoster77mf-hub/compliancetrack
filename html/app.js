document.addEventListener('DOMContentLoaded', () => {
  // Emoji favicon + visible emoji element
  const emojiFavicon = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"%3E%3Ctext x="50" y="70" font-size="70' +
    '" text-anchor="middle" font-family="Apple Color Emoji, Segoe UI Emoji, Noto Color Emoji, EmojiOne Color, sans-serif"%' +
    '3E🎌%3C/text%3E%3C/svg%3E';

  const link = document.createElement('link');
  link.rel = 'icon';
  link.type = 'image/svg+xml';
  link.href = emojiFavicon;
  document.head.appendChild(link);

  const emojiEl = document.createElement('span');
  emojiEl.textContent = '🎌';
  emojiEl.style.cssText = 'font-size: 28px; margin-right: 8px; display: inline-block; vertical-align: middle;';
  document.querySelector('.logo')?.prepend(emojiEl);

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
