document.addEventListener('DOMContentLoaded', () => {
    const views = {
        scanning: document.getElementById('scanning-view'),
        result: document.getElementById('result-view'),
        error: document.getElementById('error-view'),
    };
    const showView = (viewName) => {
        Object.values(views).forEach(v => v.classList.remove('active'));
        views[viewName].classList.add('active');
    };

    const renderProgress = (progress) => {
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');
        if (!progress) return;
        
        let percentage = 0;
        if (progress.total > 0) {
            percentage = (progress.processed / progress.total) * 100;
        }
        
        progressBar.style.width = `${percentage}%`;
        progressBar.textContent = `${Math.round(percentage)}%`;
        progressText.textContent = progress.status || 'Processing...';
    };

    const formatExplanation = (text) => {
        if (!text) return 'No AI explanation available.';
        return text.split('\n').filter(line => line.startsWith('*')).map(line => `<li>${line.substring(1).trim()}</li>`).join('') || `<p>${text}</p>`;
    };
    
    const renderResult = (result) => {
        document.getElementById('video-verdict').textContent = result.verdict || 'N/A';
        document.getElementById('video-verdict').className = `verdict ${result.verdict}`;
        document.getElementById('video-confidence').textContent = result.average_confidence !== undefined ? `${(result.average_confidence * 100).toFixed(2)}%` : 'N/A';
        document.getElementById('video-explanation').innerHTML = `<ul>${formatExplanation(result.video_explanation)}</ul>`;
        
        document.getElementById('audio-verdict').textContent = result.audio_verdict || 'N/A';
        document.getElementById('audio-verdict').className = `verdict ${result.audio_verdict.replace(/\s+/g, '-')}`;
        document.getElementById('audio-confidence').textContent = result.audio_confidence !== undefined ? `${(result.audio_confidence * 100).toFixed(2)}%` : 'N/A';
        document.getElementById('audio-explanation').innerHTML = `<ul>${formatExplanation(result.audio_explanation)}</ul>`;
        
        if (result.result_image) {
            document.getElementById('result-image').src = `data:image/jpeg;base64,${result.result_image}`;
        }
    };
    
    const updateUI = (state) => {
        if (!state) return;
        if (state.status === 'scanning') {
            renderProgress(state.progress);
            showView('scanning');
        } else if (state.status === 'complete') {
            renderResult(state.result);
            showView('result');
        } else if (state.status === 'error') {
            document.getElementById('error-box').textContent = state.error || 'An unknown error occurred.';
            showView('error');
        }
    };

    // Initial load
    chrome.storage.local.get('scanState', (data) => updateUI(data.scanState));

    // Listen for updates from the background script
    chrome.storage.onChanged.addListener((changes, namespace) => {
        if (namespace === 'local' && changes.scanState) {
            updateUI(changes.scanState.newValue);
        }
    });
});