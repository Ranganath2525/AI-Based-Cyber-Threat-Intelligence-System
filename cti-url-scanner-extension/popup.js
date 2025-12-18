// --- DOM Elements ---
const loginView = document.getElementById('login-view');
const mainView = document.getElementById('main-view');
const status = document.getElementById('status');
const loginBtn = document.getElementById('loginBtn');
const scanEmailBtn = document.getElementById('scanEmailBtn');
const logoutBtn = document.getElementById('logoutBtn');
const loggedInUser = document.getElementById('loggedInUser');
const analyzeVideoBtn = document.getElementById('analyzeVideoBtn');
const liveScanBtn = document.getElementById('liveScanBtn');
const newVideoScanBtn = document.getElementById('new-video-scan-button');
const clearResultsBtn = document.getElementById('clear-results-btn');

// --- EVENT LISTENERS ---
document.addEventListener('DOMContentLoaded', async () => {
    const result = await chrome.storage.sync.get(['jwtToken', 'username']);
    if (result.jwtToken && result.username) {
        showMainView(result.username);
    } else {
        showLoginView();
    }
    
    chrome.runtime.sendMessage({ type: 'get-status' }, (response) => {
        if (response && response.isRecording) {
            liveScanBtn.disabled = true;
            liveScanBtn.textContent = 'Live Analysis in Progress...';
        }
    });

    // Set initial UI state on popup open
    chrome.storage.local.get(['videoScanState', 'lastScanResult'], (data) => {
        if (data.videoScanState) {
            updateVideoUI(data.videoScanState);
        }
        if (data.lastScanResult) {
            updateEmailUI(data.lastScanResult);
        }
    });
});

clearResultsBtn.addEventListener('click', () => {
    chrome.storage.local.remove(['lastScanResult', 'videoScanState'], () => {
        // Hide the results containers immediately
        document.getElementById('email-scan-results-container').classList.add('hidden');
        document.getElementById('video-result-view').classList.add('hidden');
        // Optional: show a status message
        status.textContent = 'Results cleared.';
        setTimeout(() => { status.textContent = ''; }, 2000);
    });
});

liveScanBtn.addEventListener('click', () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs.length === 0) {
            status.textContent = "Cannot find active tab.";
            return;
        }
        const tabId = tabs[0].id;
        liveScanBtn.disabled = true;
        liveScanBtn.textContent = 'Starting Recording...';
        const selectedTime = document.getElementById('recording-time-select').value;
        chrome.runtime.sendMessage({
            type: 'start-recording',
            duration: parseInt(selectedTime, 10),
            tabId: tabId
        });
        setTimeout(() => window.close(), 1500);
    });
});

loginBtn.addEventListener('click', async () => {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value.trim();
    if (!username || !password) { status.textContent = "Username/password required."; return; }
    status.textContent = "Logging in...";
    loginBtn.disabled = true;
    try {
        const response = await fetch('http://127.0.0.1:5000/ext/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error);
        await chrome.storage.sync.set({ jwtToken: data.token, username: username });
        showMainView(username);
    } catch (error) {
        status.textContent = `Login failed: ${error.message}`;
    } finally {
        loginBtn.disabled = false;
    }
});

logoutBtn.addEventListener('click', async () => {
    await chrome.storage.sync.remove(['jwtToken', 'username']);
    await chrome.storage.local.remove(['lastScanResult', 'videoScanState']);
    showLoginView();
});

// --- Restored Manual Scan Button Logic ---
scanEmailBtn.addEventListener('click', () => {
    scanEmailBtn.disabled = true;
    scanEmailBtn.textContent = 'Extracting Content...';
    status.textContent = ''; // Clear previous status
    document.getElementById('email-scan-results-container').classList.add('hidden'); // Hide old results

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs.length === 0) {
            status.textContent = "Error: Could not find the active tab.";
            scanEmailBtn.disabled = false;
            scanEmailBtn.textContent = 'Scan Current Email';
            return;
        }
        const tabId = tabs[0].id;

        // 1. Execute content script to extract data from the page
        chrome.scripting.executeScript({
            target: { tabId: tabId },
            files: ['content_scanner.js']
        }).then(() => {
            // 2. Send message to the content script to start the extraction
            chrome.tabs.sendMessage(tabs[0].id, { action: "scan_links" }, (response) => {
                if (chrome.runtime.lastError) {
                    status.textContent = `Error: ${chrome.runtime.lastError.message}`;
                    scanEmailBtn.disabled = false;
                    scanEmailBtn.textContent = 'Scan Current Email';
                    return;
                }

                // 3. Handle response from content script
                if (response && response.status === 'data_extracted') {
                    scanEmailBtn.textContent = 'Analyzing...';
                    // 4. Send the extracted data to the background script for API call
                    chrome.runtime.sendMessage({
                        action: 'scan_links', 
                        email_text: response.data.emailText,
                        urls: response.data.urls,
                        tabId: tabId // Pass the tab ID to the background script
                    }, (bg_response) => {
                        // The background script will handle the analysis and save to storage.
                        // The storage listener will update the UI.
                        if (chrome.runtime.lastError) {
                             status.textContent = `Error: ${chrome.runtime.lastError.message}`;
                        } else if (bg_response && bg_response.status === 'error') {
                            status.textContent = `Analysis Error: ${bg_response.message}`;
                        }
                        // We don't need to do anything here on success, the storage listener handles it.
                        scanEmailBtn.disabled = false;
                        scanEmailBtn.textContent = 'Scan Current Email';
                    });
                } else {
                    status.textContent = (response && response.message) ? response.message : 'Failed to extract content from page.';
                    scanEmailBtn.disabled = false;
                    scanEmailBtn.textContent = 'Scan Current Email';
                }
            });
        }).catch(err => {
            status.textContent = `Failed to inject scanner: ${err.message}`;
            scanEmailBtn.disabled = false;
            scanEmailBtn.textContent = 'Scan Current Email';
        });
    });
});

analyzeVideoBtn.addEventListener('click', () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        const url = tabs[0].url;
        if (url && url.startsWith('http')) {
            const initialState = { status: 'scanning', url: url, progress: { message: 'Initiating scan...' } };
            chrome.storage.local.set({ videoScanState: initialState });
            chrome.runtime.sendMessage({ action: 'initiateVideoScan', url: url });
        } else {
            status.textContent = 'A valid page URL is required.';
        }
    });
});

newVideoScanBtn.addEventListener('click', () => {
    chrome.storage.local.remove('videoScanState');
});

// --- UI Functions ---
function showLoginView() { loginView.classList.remove('hidden'); mainView.classList.add('hidden'); } 
function showMainView(username) { loginView.classList.add('hidden'); mainView.classList.remove('hidden'); loggedInUser.textContent = username; }

const videoInitialView = document.getElementById('video-initial-view');
const videoScanningView = document.getElementById('video-scanning-view');
const videoResultView = document.getElementById('video-result-view');
const videoProgressBar = document.getElementById('video-progress-bar');
const videoProgressText = document.getElementById('video-progress-text');

function formatExplanation(text) {
    if (!text || typeof text !== 'string') return '<p>No explanation available.</p>';
    const formatted = text.replace(/\*/g, '•').replace(/\n/g, '<br>');
    return `<p style="margin-top: 5px;">${formatted}</p>`;
}

function updateVideoUI(state) {
    if (!state || !state.status) {
        videoInitialView.classList.remove('hidden');
        videoScanningView.classList.add('hidden');
        videoResultView.classList.add('hidden');
        return;
    }

    switch (state.status) {
        case 'scanning':
            videoInitialView.classList.add('hidden');
            videoScanningView.classList.remove('hidden');
            videoResultView.classList.add('hidden');
            document.getElementById('video-scanning-url').textContent = state.url;
            const progress = state.progress || {};
            videoProgressText.textContent = progress.message || progress.status || 'Scanning...';
            const percentage = (progress.processed && progress.total) ? (progress.processed / progress.total) * 100 : 0;
            videoProgressBar.style.width = `${percentage}%`;
            videoProgressBar.textContent = percentage ? `${Math.round(percentage)}%` : '';
            break;
        case 'complete':
            videoInitialView.classList.add('hidden');
            videoScanningView.classList.add('hidden');
            videoResultView.classList.remove('hidden');
            const result = state.result || {};
            let content = `<p><strong>Video Prediction:</strong> ${result.video_prediction || 'N/A'}</p>`;
            content += `<p><strong>Audio Prediction:</strong> ${result.audio_prediction || 'N/A'}</p>`;
            if (result.video_explanation) content += `<div><strong>Video Details:</strong> ${formatExplanation(result.video_explanation)}</div>`;
            if (result.audio_explanation) content += `<div><strong>Audio Details:</strong> ${formatExplanation(result.audio_explanation)}</div>`;
            document.getElementById('video-result-content').innerHTML = content;
            break;
        case 'error':
            videoInitialView.classList.add('hidden');
            videoScanningView.classList.add('hidden');
            videoResultView.classList.remove('hidden');
            document.getElementById('video-result-content').innerHTML = `<p style="color: red;"><strong>Error:</strong> ${state.error || 'An unknown error occurred.'}</p>`;
            break;
    }
}

function updateEmailUI(result) {
    const container = document.getElementById('email-scan-results-container');
    if (!result) {
        container.classList.add('hidden');
        return;
    }

    let html = '<h4>Email Scan Report</h4>';

    if (result.email_verdict) {
        html += `<p><strong>Email Verdict:</strong> ${result.email_verdict}</p>`;
        if (result.email_explanation) {
            html += `<div><strong>Explanation:</strong> ${formatExplanation(result.email_explanation)}</div>`;
        }
    }

    if (result.url_results && result.url_results.length > 0) {
        html += '<details style="margin-top: 10px;">';
        html += `<summary style="cursor: pointer; font-weight: bold;">View Detected URLs (${result.url_results.length})</summary>`;
        html += '<div style="padding-left: 15px; border-left: 2px solid #eee; margin-top: 5px; max-height: 150px; overflow-y: auto;">';
        result.url_results.forEach(urlRes => {
            html += `<div style="border-top: 1px solid #eee; padding: 5px 0;">
                        <p style="word-wrap: break-word; margin: 0;"><strong>URL:</strong> ${urlRes.url}</p>
                        <p style="margin: 0;"><strong>Verdict:</strong> ${urlRes.verdict} | <strong>Risk:</strong> ${urlRes.risk_score}%</p>
                     </div>`;
        });
        html += '</div></details>';
    }

    container.innerHTML = html;
    container.classList.remove('hidden');
}

// Listen for changes in storage and update UI
chrome.storage.onChanged.addListener((changes, namespace) => {
    if (namespace === 'local') {
        if (changes.videoScanState) {
            updateVideoUI(changes.videoScanState.newValue);
        }
        if (changes.lastScanResult) {
            updateEmailUI(changes.lastScanResult.newValue);
        }
    }
});