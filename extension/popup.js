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

  loadNews();
}

async function loadNews() {
  const { latestNews } = await chrome.storage.local.get('latestNews');
  const container = document.getElementById('newsContainer');
  container.innerHTML = '';

  if (!latestNews) {
    container.textContent = 'Fetching…';
    // Force an immediate fetch (use same logic as background)
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

  render(latestNews);
}

function render(articles) {
  const container = document.getElementById('newsContainer');
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