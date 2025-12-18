document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const views = {
        initial: document.getElementById('initial-view'),
        scanning: document.getElementById('scanning-view'),
        result: document.getElementById('result-view'),
    };
    const scanButton = document.getElementById('scan-button');
    const newScanButton = document.getElementById('new-scan-button');
    const cancelScanButton = document.getElementById('cancel-scan-button'); // New button
    const initialError = document.getElementById('initial-error');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');

    // --- Functions ---
    const showView = (viewName) => {
        Object.values(views).forEach(view => view.style.display = 'none');
        if (views[viewName]) views[viewName].style.display = 'block';
    };

    const renderProgress = (progress) => {
        if (!progress) return;
        progressText.textContent = progress.message || 'Processing...';
        if (typeof progress.current === 'number' && typeof progress.total === 'number' && isFinite(progress.current) && isFinite(progress.total)) {
            progressBar.value = progress.current;
            progressBar.max = progress.total;
            progressText.textContent = `${progress.message} (${progress.current} / ${progress.total} frames)`;
        } else {
            progressBar.removeAttribute('value'); // Indeterminate progress
            progressBar.value = 0; // Reset value for indeterminate state
            progressBar.max = 1;   // Reset max for indeterminate state
        }
    };

    const renderResult = (data) => {
        if (!data) return;
        document.getElementById('video-verdict').textContent = data.video_prediction;
        document.getElementById('video-verdict').className = `verdict ${data.video_prediction}`;
        if (data.video_confidence !== undefined) {
            document.getElementById('video-confidence').textContent = `${(data.video_confidence * 100).toFixed(2)}%`;
        }

        document.getElementById('video-explanation').innerHTML = formatExplanation(data.video_explanation);
        
        document.getElementById('audio-verdict').textContent = data.audio_prediction;
        document.getElementById('audio-verdict').className = `verdict ${data.audio_prediction}`;
        if (data.audio_confidence !== undefined) {
            document.getElementById('audio-confidence').textContent = `${(data.audio_confidence * 100).toFixed(2)}%`;
        }

        document.getElementById('audio-explanation').innerHTML = formatExplanation(data.audio_explanation);
        showView('result');
    };

    const formatExplanation = (explanation) => {
        if (!explanation) return '<p>No explanation provided.</p>';
        const points = explanation.split('\n').filter(p => p.startsWith('*')).map(p => `<li>${p.substring(1).trim()}</li>`).join('');
        return `<ul>${points}</ul>`;
    };

    // --- Event Listeners ---
    scanButton.addEventListener('click', () => {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            const url = tabs[0].url;
            // Basic URL validation
            if (url && (url.startsWith('http') || url.startsWith('https'))) {
                initialError.textContent = '';
                // Set initial scanning state and UI
                const initialState = { status: 'scanning', url: url, progress: { message: 'Initiating scan...' } };
                chrome.storage.local.set({ scanState: initialState }, () => {
                    chrome.runtime.sendMessage({ action: 'initiateScan', url: url });
                    document.getElementById('scanning-url').textContent = url;
                    renderProgress(initialState.progress);
                    showView('scanning');
                });
            } else {
                initialError.textContent = 'A valid page URL is required. Please navigate to a video and try again.';
            }
        });
    });

    newScanButton.addEventListener('click', () => {
        chrome.storage.local.remove('scanState', () => {
            showView('initial');
        });
    });

    cancelScanButton.addEventListener('click', () => {
        // Simply remove the state. The backend won't be cancelled, but the UI will reset.
        chrome.storage.local.remove('scanState', () => {
            showView('initial');
        });
    });

    // Listen for changes in storage, which is how the background script now communicates.
    chrome.storage.onChanged.addListener((changes, namespace) => {
        if (namespace === 'local' && changes.scanState) {
            const newState = changes.scanState.newValue;
            if (!newState) { // State was removed
                showView('initial');
                return;
            }
            updateUI(newState);
        }
    });

    // --- UI Update Functions ---
    const updateUI = (state) => {
        if (state.status === 'scanning') {
            document.getElementById('scanning-url').textContent = state.url;
            renderProgress(state.progress);
            showView('scanning');
        } else if (state.status === 'complete') {
            renderResult(state.result);
        }
    };

    // --- Initialization ---
    // When the popup opens, get the current state from storage and update the UI.
    chrome.storage.local.get('scanState', (data) => {
        if (data.scanState) {
            updateUI(data.scanState);
        } else {
            showView('initial');
        }
    });
});
