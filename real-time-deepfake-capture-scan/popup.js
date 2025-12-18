document.addEventListener('DOMContentLoaded', () => {
  const startBtn = document.getElementById('startBtn');
  const status = document.getElementById('status');

  // Check for JWT token to see if user is logged in
  chrome.storage.sync.get(['jwtToken'], (result) => {
    if (!result.jwtToken) {
      startBtn.disabled = true;
      status.innerHTML = '<b>Login Required.</b><br>Please log in via the main CTI extension popup first.';
    }
  });

  // Ask background script for current recording status
  chrome.runtime.sendMessage({ type: 'get-status' }, (response) => {
    if (response && response.isRecording) {
      startBtn.disabled = true;
      status.textContent = 'Analysis in progress...';
    }
  });

  startBtn.addEventListener('click', () => {
    startBtn.disabled = true;
    status.textContent = 'Starting recording...';
    chrome.runtime.sendMessage({ type: 'start-recording' });
    setTimeout(() => window.close(), 1500);
  });
});