document.addEventListener('DOMContentLoaded', init);

async function init() {
  // Load saved IP
  const { backendIP } = await chrome.storage.sync.get('backendIP');
  if (backendIP) document.getElementById('ipInput').value = backendIP;

  document.getElementById('saveBtn').addEventListener('click', async () => {
    const ip = document.getElementById('ipInput').value.trim();
    await chrome.storage.sync.set({ backendIP: ip });
    loadNews(); // immediate refresh
  });

  // New button: manually trigger an immediate fetch regardless of cached data
  document.getElementById('refreshBtn').addEventListener('click', async () => {
    // Clear cached news so loadNews will perform a fresh request
    await chrome.storage.local.remove('latestNews');
  loadNews();
  });

  // Open the optional self‑hosted site in a new tab
  document.getElementById('openSiteBtn').addEventListener('click', async () => {
    const { siteUrl } = await chrome.storage.sync.get('siteUrl');
    if (siteUrl) {
      // Use chrome.tabs.create to open a new tab (requires "tabs" permission)
      chrome.tabs.create({ url: siteUrl });
    } else {
  const container = document.getElementById('newsContainer');
      container.textContent = 'No site URL configured – set it in the extension options.';
    }
  });

  loadNews();
}

async function loadNews() {
  const { latestNews } = await chrome.storage.local.get('latestNews');
  const container = document.getElementById('newsContainer');
  container.innerHTML = '';

  // If we don't have cached news, fetch it now.
  if (!latestNews) {
    container.textContent = 'Fetching…';
    const { backendIP } = await chrome.storage.sync.get('backendIP');
    if (!backendIP) return;
    try {
      const resp = await fetch(`http://${backendIP}:8000/news`);
      const data = await resp.json();
      await chrome.storage.local.set({ latestNews: data });
      render(data);
    } catch (e) {
      container.textContent = '❌ Could not load news.';
    }
    return;
  }

  // Cached data is stored as the whole API response (object with an "articles" array).
  render(latestNews);
}

/** Render the news payload.
 *  The payload can be:
 *   • the raw FastAPI response object: { articles: [...] }
 *   • a plain array of article objects (some callers may return that directly)
 *   • anything else (null, string, etc.) – in which case we show a friendly message.
 */
function render(response) {
  const container = document.getElementById('newsContainer');
  // Normalise to an array of article objects
  let articles = [];
  if (Array.isArray(response)) {
    articles = response;
  } else if (response && Array.isArray(response.articles)) {
    articles = response.articles;
  }

  if (!articles.length) {
    container.textContent = 'No articles available.';
    return;
  }
  articles.forEach(a => {
    const div = document.createElement('div');
    div.className = 'article';
    div.innerHTML = `
      <div class="title"><a href="${a.url}" target="_blank">${a.title}</a></div>
      <div class="summary">${a.summary}</div>
      <div class="rating">${'🐶'.repeat(a.rating)}</div>
    `;
    container.appendChild(div);
  });
}