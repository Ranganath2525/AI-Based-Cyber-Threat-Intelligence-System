const OFFSCREEN_DOCUMENT_PATH = '/offscreen.html';
const RECORDING_DURATION_S = 30;
const API_ENDPOINT = 'http://127.0.0.1:5000/ext/analyze_recorded_video';

let isRecording = false;
let countdownInterval;

// Helper to read the streamed response from the backend
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
                } catch (e) {
                    console.error('Error parsing stream data:', e, 'Line:', line);
                }
            }
        }
    }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'start-recording') {
    if (isRecording) return false;
    isRecording = true;
    startRecordingSequence();
    sendResponse({ success: true });
    return true;

  } else if (message.type === 'upload-video') {
    clearInterval(countdownInterval);
    chrome.action.setBadgeText({ text: '...' });
    
    (async () => {
      // 1. Get auth token
      const { jwtToken } = await chrome.storage.sync.get('jwtToken');
      if (!jwtToken) {
        chrome.notifications.create({ type: 'basic', iconUrl: 'icon128.png', title: 'Authentication Error', message: 'Could not find login token. Please log in first.' });
        isRecording = false;
        chrome.action.setBadgeText({ text: '' });
        return;
      }
      
      // 2. Convert dataURL back to Blob for efficient upload
      const response = await fetch(message.dataUrl);
      const blob = await response.blob();
      
      const formData = new FormData();
      formData.append('video', blob, 'live-recording.webm');
      
      // 3. Open results page and start upload
      chrome.tabs.create({ url: 'results.html' });

      try {
        const fetchResponse = await fetch(API_ENDPOINT, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${jwtToken}` },
          body: formData,
        });

        if (!fetchResponse.ok) {
          throw new Error(`HTTP error! status: ${fetchResponse.status}`);
        }
        
        // 4. Handle streaming results
        await readStream(fetchResponse.body, (event) => {
          console.log('Background: Received stream event:', event);
          let stateUpdate = {};
          if (event.type === 'progress') {
            stateUpdate = { status: 'scanning', progress: event };
          } else if (event.type === 'result') {
            stateUpdate = { status: 'complete', result: event };
          } else if (event.type === 'video_explanation' || event.type === 'audio_explanation') {
            // This is a bit tricky, we need to update the existing result
            chrome.storage.local.get('scanState', (data) => {
              if (data.scanState && data.scanState.status === 'complete') {
                  const updatedState = data.scanState;
                  if(event.type === 'video_explanation') updatedState.result.video_explanation = event.explanation;
                  if(event.type === 'audio_explanation') updatedState.result.audio_explanation = event.explanation;
                  chrome.storage.local.set({ scanState: updatedState });
              }
            });
            return; // Skip the generic state update below
          } else if (event.type === 'error') {
            stateUpdate = { status: 'error', error: event.message };
          }
          chrome.storage.local.set({ scanState: stateUpdate });
        });

      } catch (error) {
        console.error('Error during analysis stream:', error);
        chrome.storage.local.set({ scanState: { status: 'error', error: error.message } });
      } finally {
        isRecording = false;
        chrome.action.setBadgeText({ text: '' });
        closeOffscreenDocument();
      }
    })();
    return true;

  } else if (message.type === 'get-status') {
    sendResponse({ isRecording: isRecording });
    return true;
  }
});

async function startRecordingSequence() {
  await setupOffscreenDocument();
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  try {
    const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id });
    startBadgeCountdown();
    chrome.runtime.sendMessage({
      type: 'start-offscreen-recording',
      target: 'offscreen',
      streamId: streamId,
      duration: RECORDING_DURATION_S * 1000,
    });
  } catch (error) {
    console.error("Failed to start recording:", error);
    isRecording = false;
    chrome.action.setBadgeText({ text: '' });
  }
}

function startBadgeCountdown() {
  let remaining = RECORDING_DURATION_S;
  chrome.action.setBadgeBackgroundColor({ color: '#FF0000' });
  countdownInterval = setInterval(() => {
    chrome.action.setBadgeText({ text: `${remaining}` });
    remaining--;
    if (remaining < 0) clearInterval(countdownInterval);
  }, 1000);
}

// Offscreen Document Helpers
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