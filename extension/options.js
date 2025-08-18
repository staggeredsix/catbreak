document.addEventListener('DOMContentLoaded', async () => {
  const { backendIP, siteUrl } = await chrome.storage.sync.get(['backendIP', 'siteUrl']);
  if (backendIP) document.getElementById('backendIp').value = backendIP;
  if (siteUrl) document.getElementById('siteUrl').value = siteUrl;

  document.getElementById('saveBtn').addEventListener('click', async () => {
    const backendIP = document.getElementById('backendIp').value.trim();
    const siteUrl = document.getElementById('siteUrl').value.trim();
    await chrome.storage.sync.set({ backendIP, siteUrl });
    const status = document.getElementById('status');
    status.style.color = 'green';
    status.textContent = 'Settings saved.';
    setTimeout(() => (status.textContent = ''), 2000);
  });
});
