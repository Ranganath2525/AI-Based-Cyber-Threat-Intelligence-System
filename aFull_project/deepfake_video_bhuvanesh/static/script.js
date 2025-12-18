document.addEventListener('DOMContentLoaded', () => {
    // DOM Element References
    const uploadState = document.getElementById('upload-state');
    const videoInput = document.getElementById('video-input');
    const dragDropArea = document.getElementById('drag-drop-area');
    const progressArea = document.getElementById('progress-area');
    const resultArea = document.getElementById('result-area');
    const errorArea = document.getElementById('error-area');
    const verdictText = document.getElementById('verdict-text');
    const videoScoreText = document.getElementById('video-score-text');
    const errorText = document.getElementById('error-text');
    const resetButton = document.getElementById('reset-button');
    const errorResetButton = document.getElementById('error-reset-button');

    // State manager to show/hide different sections
    const showState = (state) => {
        uploadState.classList.add('hidden');
        progressArea.classList.add('hidden');
        resultArea.classList.add('hidden');
        errorArea.classList.add('hidden');
        if (state === 'upload') uploadState.classList.remove('hidden');
        else if (state === 'progress') progressArea.classList.remove('hidden');
        else if (state === 'result') resultArea.classList.remove('hidden');
        else if (state === 'error') errorArea.classList.remove('hidden');
    };

    const handleFile = (file) => {
        if (!file || !file.type.startsWith('video/')) {
            showError('Please upload a valid video file.');
            return;
        }
        
        // --- Show Progress Bar ---
        // When the file is handled, we immediately show the progress spinner.
        showState('progress'); 
        
        const formData = new FormData();
        formData.append('video', file);

        fetch('/predict', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json().then(data => ({ ok: response.ok, data })))
        .then(({ ok, data }) => {
            if (!ok) {
                throw new Error(data.error || 'An unknown server error occurred.');
            }
            // When the long analysis is done, hide the progress bar and show the result.
            showResult(data);
        })
        .catch(error => {
            showError(`Prediction Error: ${error.message}`);
        });
    };

    const showResult = (data) => {
        verdictText.textContent = data.final_verdict;
        videoScoreText.textContent = `Average Fake Confidence: ${(data.average_confidence * 100).toFixed(2)}%`;
        
        verdictText.className = 'verdict'; // Reset classes
        verdictText.classList.add(data.final_verdict === 'REAL' ? 'real' : 'fake');
        
        showState('result');
    };

    const showError = (message) => {
        errorText.textContent = message;
        showState('error');
    };
    
    // --- Event Listeners ---
    dragDropArea.addEventListener('click', () => videoInput.click());
    videoInput.addEventListener('change', () => { if (videoInput.files.length > 0) handleFile(videoInput.files[0]); });
    ['dragenter', 'dragover'].forEach(eventName => {
        dragDropArea.addEventListener(eventName, (e) => { e.preventDefault(); dragDropArea.classList.add('drag-over'); });
    });
    ['dragleave', 'drop'].forEach(eventName => {
        dragDropArea.addEventListener(eventName, (e) => { e.preventDefault(); dragDropArea.classList.remove('drag-over'); });
    });
    dragDropArea.addEventListener('drop', (e) => {
        if (e.dataTransfer.files.length > 0) { videoInput.files = e.dataTransfer.files; handleFile(e.dataTransfer.files[0]); }
    });
    resetButton.addEventListener('click', () => showState('upload'));
    errorResetButton.addEventListener('click', () => showState('upload'));

    // --- Theme Switcher Logic ---
    const themeToggle = document.getElementById('checkbox');
    const currentTheme = localStorage.getItem('theme');
    if (currentTheme) {
        document.documentElement.setAttribute('data-theme', currentTheme);
        if (currentTheme === 'dark') { themeToggle.checked = true; }
    }
    themeToggle.addEventListener('change', () => {
        const theme = themeToggle.checked ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    });
});