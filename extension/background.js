// Set up an hourly alarm that triggers a fetch to the backend.
// The alarm runs even when the popup is closed.
chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create('fetchNews', { periodInMinutes: 60 });
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === 'fetchNews') {
    const ip = await getBackendIP();
    if (!ip) return; // not configured yet
    try {
      const resp = await fetch(`http://${ip}:8000/news`);
      if (!resp.ok) throw new Error('Network error');
      const data = await resp.json();
      // Store the latest news for the popup to read.
      await chrome.storage.local.set({ latestNews: data });
      // Optional: show a subtle notification each hour.
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/puppy-5.png',
        title: '🐾 New Feel‑Good News!',
        message: 'Your hourly dose of happiness is ready.'
      });
    } catch (e) {
      console.error('Failed to fetch news:', e);
    }
  }
});

async function getBackendIP() {
  const { backendIP } = await chrome.storage.sync.get('backendIP');
  return backendIP;
}