console.log("Background script loaded (v2 - Manual & Auto).");

// --- PART 1: LOGIC FROM THE LIVE RECORDER EXTENSION ---
const OFFSCREEN_DOCUMENT_PATH = '/offscreen.html';
const API_ENDPOINT = 'http://127.0.0.1:5000/ext/analyze_recorded_video';

let isRecording = false;
let countdownInterval;

async function setupOffscreenDocument() {
  if (!(await chrome.offscreen.hasDocument())) {
    await chrome.offscreen.createDocument({
      url: OFFSCREEN_DOCUMENT_PATH,
      reasons: ['USER_MEDIA'],
      justification: 'Recording tab for deepfake analysis.',
    });
  }
}

async function closeOffscreenDocument() {
  if (await chrome.offscreen.hasDocument()) {
    await chrome.offscreen.closeDocument();
  }
}

async function startRecordingSequence(durationInSeconds, tabId) {
  if (!tabId) {
    console.error("Failed to start recording: No tab ID provided.");
    isRecording = false;
    return;
  }
  await setupOffscreenDocument();
  try {
    const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tabId });
    startBadgeCountdown(durationInSeconds);
    chrome.runtime.sendMessage({
      type: 'start-offscreen-recording',
      target: 'offscreen',
      streamId: streamId,
      duration: durationInSeconds * 1000,
    });
  } catch (error) {
    console.error("Failed to start recording:", error);
    isRecording = false;
    chrome.action.setBadgeText({ text: '' });
  }
}

function startBadgeCountdown(durationInSeconds) {
  let remaining = durationInSeconds;
  chrome.action.setBadgeBackgroundColor({ color: '#FF0000' });
  countdownInterval = setInterval(() => {
    chrome.action.setBadgeText({ text: `${remaining}` });
    remaining--;
    if (remaining < 0) clearInterval(countdownInterval);
  }, 1000);
}


// --- PART 2: LOGIC FROM THE CTI-URL-SCANNER EXTENSION ---
async function readStream(stream, onData) {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();
        for (const line of lines) {
            if (line.startsWith('data: ')) {
                try {
                    const json = JSON.parse(line.substring(6));
                    onData(json);
                } catch (e) { console.error('Error parsing stream data:', e, 'Line:', line); }
            }
        }
    }
}

async function handleEmailScan(content, tabId, sendResponse) {
    try {
        const {jwtToken} = await chrome.storage.sync.get('jwtToken');
        if (!jwtToken) { throw new Error("Not logged in"); }
        const payload = { email_text: content.email_text, urls: content.urls };
        const response = await fetch('http://127.0.0.1:5000/ext/analyze_email_content', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${jwtToken}` },
            body: JSON.stringify(payload)
        });

        // If the token is invalid or expired, the server will return 401 or 403
        if (response.status === 401 || response.status === 403) {
            // Clear the bad token and notify the user
            await chrome.storage.sync.remove('jwtToken');
            await chrome.storage.local.remove('lastScanResult');
            chrome.notifications.create({
                type: 'basic',
                iconUrl: 'icon128.png',
                title: 'CTI Scanner: Authentication Error',
                message: 'Your session has expired. Please log in again via the extension popup.',
                priority: 2
            });
            return;
        }

        const data = await response.json();
        if (!response.ok) { throw new Error(data.error || `Server error: ${response.status}`); }
        chrome.storage.local.set({ lastScanResult: data });

        // Create a more informative notification
        const maliciousLinks = data.url_results?.filter(r => r.verdict === 'Malicious');
        let notificationTitle;
        let notificationMessage = 'Open the CTI Scanner extension for the full report.';

        if (maliciousLinks && maliciousLinks.length > 0) {
            notificationTitle = `🚨 Warning: ${maliciousLinks.length} Malicious Link(s) Found! 🚨`;
            notificationMessage = `Example: ${maliciousLinks[0].url}. Check the extension for a full list.`
        } else {
            notificationTitle = `CTI Email Scan: ${data.email_verdict || 'Scan Complete'}`;
        }

        chrome.notifications.create({
            type: 'basic',
            iconUrl: 'icon128.png',
            title: notificationTitle,
            message: notificationMessage,
            priority: 2
        });

        if (data.url_results && tabId) {
            chrome.scripting.executeScript({
                target: { tabId: tabId },
                func: injectLinkDecorations,
                args: [data.url_results]
            });
        }
        if (sendResponse) sendResponse({ status: 'complete', data: data });
    } catch (error) {
        console.error("Email scan failed:", error);
        if (sendResponse) sendResponse({ status: 'error', message: error.message });
    }
}

function injectLinkDecorations(results) {
    const emailBodySelectors = ['.a3s.aiL', '.ii.gt', '.WordSection1', 'div[aria-label="Message body"]'];
    let emailBody = null;
    for (const selector of emailBodySelectors) {
        emailBody = document.querySelector(selector);
        if (emailBody) break;
    }
    if (!emailBody) return;
    emailBody.querySelectorAll('.cti-scan-icon').forEach(icon => icon.remove());
    const linkElements = emailBody.querySelectorAll('a[href]');
    linkElements.forEach(link => {
        const result = results.find(r => r.url === link.href);
        if (result) {
            const icon = document.createElement('span');
            icon.className = 'cti-scan-icon';
            icon.style.marginLeft = '5px';
            icon.style.cursor = 'help';
            icon.style.fontSize = '1.2em';
            icon.textContent = result.verdict === 'Malicious' ? '🚨' : '✅';
            icon.title = result.verdict === 'Malicious' ? `CTI VERDICT: MALICIOUS\nRisk Score: ${result.risk_score}%` : 'CTI VERDICT: SAFE';
            if (link.parentNode) {
                link.parentNode.insertBefore(icon, link.nextSibling);
            }
        }
    });
}

async function handleVideoScan(url) {
    console.log(`Initiating video scan for URL: ${url}`);
    chrome.storage.local.set({ videoScanState: { status: 'scanning', url: url, progress: { message: 'Contacting server...' } } });

    try {
        const { jwtToken } = await chrome.storage.sync.get('jwtToken');
        if (!jwtToken) {
            throw new Error("Not logged in. Please log in via the extension popup.");
        }

        const response = await fetch('http://127.0.0.1:5000/ext/predict_video_extension', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${jwtToken}`
            },
            body: JSON.stringify({ url: url })
        });

        if (!response.ok || !response.body) {
            throw new Error(`Server returned an error: ${response.status} ${response.statusText}`);
        }

        // Use the existing stream reader to process and store results
        await readStream(response.body, (event) => {
            if (event.type === 'progress') {
                chrome.storage.local.set({ videoScanState: { status: 'scanning', url: url, progress: event } });
            } else if (event.type === 'final_result') {
                chrome.storage.local.set({ videoScanState: { status: 'complete', url: url, result: event.data } });
            } else if (event.type === 'explanations_ready') {
                // Explanations are received after the final_result, so we need to update the existing record
                chrome.storage.local.get('videoScanState', (data) => {
                    if (data.videoScanState && data.videoScanState.status === 'complete') {
                        const updatedState = { ...data.videoScanState };
                        updatedState.result.video_explanation = event.data.video_explanation;
                        updatedState.result.audio_explanation = event.data.audio_explanation;
                        chrome.storage.local.set({ videoScanState: updatedState });
                    }
                });
            } else if (event.type === 'error') {
                throw new Error(event.message);
            }
        });

    } catch (error) {
        console.error("Video scan failed:", error);
        chrome.storage.local.set({ videoScanState: { status: 'error', url: url, error: error.message } });
    }
}

// --- LISTENERS ---

// Listen for messages from the popup or content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log("Background: Message received", message);

    if (message.type === 'start-recording') {
        if (isRecording) {
            sendResponse({ success: false, message: 'Already recording.'});
        } else {
            isRecording = true;
            startRecordingSequence(message.duration || 30, message.tabId);
            sendResponse({ success: true });
        }
        // This is a synchronous response, so we don't return true.
        return false;

    } else if (message.type === 'upload-video') {
        // This message triggers a long-running process. The popup is notified
        // immediately and then tracks progress via chrome.storage, not via this response.
        sendResponse({ status: 'Upload received, starting analysis.' });
        
        clearInterval(countdownInterval);
        chrome.action.setBadgeText({ text: '...' });

        // The async logic runs independently.
        (async () => {
            const {jwtToken} = await chrome.storage.sync.get('jwtToken');
            if (!jwtToken) {
                isRecording = false;
                chrome.action.setBadgeText({ text: '' });
                await closeOffscreenDocument();
                return;
            }
            const response = await fetch(message.dataUrl);
            const blob = await response.blob();
            const formData = new FormData();
            formData.append('video', blob, 'live-recording.webm');
            const scanUrl = 'Live Recorded Video';
            chrome.storage.local.set({ videoScanState: { status: 'scanning', url: scanUrl, progress: { message: 'Uploading...' } } });
            try {
                const fetchResponse = await fetch(API_ENDPOINT, { method: 'POST', headers: { 'Authorization': `Bearer ${jwtToken}` }, body: formData });
                if (!fetchResponse.ok) throw new Error(`HTTP error! status: ${fetchResponse.status}`);
                await readStream(fetchResponse.body, (event) => {
                    if (event.type === 'progress') {
                        chrome.storage.local.set({ videoScanState: { status: 'scanning', url: scanUrl, progress: event } });
                    } else if (event.type === 'final_result') {
                        chrome.storage.local.set({ videoScanState: { status: 'complete', url: scanUrl, result: event.data } });
                    } else if (event.type === 'explanations_ready') {
                        chrome.storage.local.get('videoScanState', (data) => {
                            if (data.videoScanState && data.videoScanState.status === 'complete') {
                                const updatedState = { ...data.videoScanState };
                                updatedState.result.video_explanation = event.data.video_explanation;
                                updatedState.result.audio_explanation = event.data.audio_explanation;
                                chrome.storage.local.set({ videoScanState: updatedState });
                            }
                        });
                    } else if (event.type === 'error') {
                        chrome.storage.local.set({ videoScanState: { status: 'error', url: scanUrl, error: event.message } });
                    }
                });
            } catch (error) {
                chrome.storage.local.set({ videoScanState: { status: 'error', url: scanUrl, error: error.message } });
            } finally {
                isRecording = false;
                chrome.action.setBadgeText({ text: '' });
                await closeOffscreenDocument();
            }
        })();
        // Synchronous response sent, so return false.
        return false;

    } else if (message.type === 'get-status') {
        sendResponse({ isRecording: isRecording });
        return false; // Synchronous response

    } else if (message.action === 'initiateVideoScan') {
        handleVideoScan(message.url);
        sendResponse({ status: 'Video scan initiated' });
        return false; // Synchronous response

    } else if (message.action === "scan_links") {
        // This action involves an async fetch to the backend, so we must return true
        // to keep the message port open for the sendResponse callback.
        const tabId = message.tabId || (sender.tab && sender.tab.id);
        if (!tabId) {
            console.error("Could not determine tab ID for email scan.");
            // Optionally send an error response if the sender is expecting one.
            if (sendResponse) {
                sendResponse({ status: 'error', message: 'Could not identify the sender tab.' });
            }
            return false; // Stop execution
        }
        handleEmailScan(message, tabId, sendResponse);
        return true;

    } else if (message.action === "auto_scan_email") {
        // This is a fire-and-forget scan triggered by our observer
        const tabId = sender.tab && sender.tab.id;
        if (tabId) {
            chrome.notifications.create({
                type: 'basic',
                iconUrl: 'icon128.png',
                title: 'CTI Auto-Scan',
                message: 'Email opened, starting automatic scan...',
                priority: 0
            });
            // We don't use sendResponse here because the content script isn't waiting for a reply.
            handleEmailScan(message, tabId, null);
        }
        return false; // No response needed
    }

    // Default return for any unhandled message types.
    return false;
});

// --- AUTO-RELOAD ON UPDATE ---
chrome.runtime.onInstalled.addListener(async (details) => {
    if (details.reason === 'update') {
        console.log("CTI Scanner updated. Reloading relevant tabs...");
        try {
            const tabs = await chrome.tabs.query({
                url: [
                    "*://mail.google.com/*",
                    "*://outlook.live.com/*"
                ]
            });

            for (const tab of tabs) {
                if (tab.id) {
                    chrome.tabs.reload(tab.id);
                    console.log(`Reloaded tab ID: ${tab.id}`);
                }
            }
        } catch (error) {
            console.error("Error reloading tabs after update:", error);
        }
    }
});
