(function () {
  const statusEl = document.getElementById('status');
  const backendLink = document.getElementById('backend-link');
  const baseUrl = window.API_BASE_URL || 'https://deepchest.onrender.com';

  if (backendLink) {
    backendLink.href = baseUrl;
    backendLink.textContent = 'Open Render Backend';
  }

  if (!statusEl) return;

  fetch(`${baseUrl}/health`)
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json().catch(() => ({}));
      statusEl.textContent = `Backend connected: ${data.status || 'ok'}`;
      statusEl.style.background = 'rgba(34, 197, 94, 0.2)';
    })
    .catch((error) => {
      statusEl.textContent = `Backend not reachable yet: ${error.message}`;
      statusEl.style.background = 'rgba(248, 113, 113, 0.2)';
    });
})();
