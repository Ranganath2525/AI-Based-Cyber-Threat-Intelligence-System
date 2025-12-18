// File: static/script.js
// --- THIS IS THE CORRECT, FULLY-FUNCTIONAL VERSION ---

document.addEventListener('DOMContentLoaded', () => {

    // --- MODAL LOGIC ---
    const historyBtn = document.getElementById('history-btn');
    const historyModal = document.getElementById('history-modal');

    if (historyBtn && historyModal) {
        const modalCloseBtn = historyModal.querySelector('.modal-close-btn');

        historyBtn.addEventListener('click', (e) => {
            e.preventDefault(); 
            historyModal.classList.remove('hidden');
        });

        if (modalCloseBtn) {
            modalCloseBtn.addEventListener('click', () => {
                historyModal.classList.add('hidden');
            });
        }
        
        historyModal.addEventListener('click', (e) => {
            if (e.target === historyModal) {
                historyModal.classList.add('hidden');
            }
        });
    }

    const statusArea = document.getElementById('status-area');
    const resultArea = document.getElementById('result-area');
    let confidenceChart = null; // Holds the Chart.js instance

    window.openTool = (evt, toolName) => {
        document.querySelectorAll(".tool-content").forEach(tc => tc.classList.remove("active"));
        document.querySelectorAll(".tab-link").forEach(tl => tl.classList.remove("active"));
        document.getElementById(toolName).classList.add("active");
        evt.currentTarget.classList.add("active");
        hideStatusAndResult();
    };

    // FIX: Restored the correct progress bar for non-video tasks.
    const showLoading = (message = "Analyzing, please wait...") => {
        statusArea.innerHTML = `<p>${message}</p><div class="indeterminate-progress-bar"></div>`;
        statusArea.classList.remove('hidden');
        resultArea.classList.add('hidden');
    };
    
    const showVideoLoading = () => {
        statusArea.innerHTML = `
            <p id="progress-text">Initializing...</p>
            <div class="progress-bar-container">
                <div id="progress-bar" style="width: 0%;"></div>
            </div>
            <p id="progress-percentage">0%</p>`;
        statusArea.classList.remove('hidden');
        resultArea.classList.add('hidden');
    };

    const hideStatusAndResult = () => {
        statusArea.classList.add('hidden');
        resultArea.classList.add('hidden');
    };

    const showResult = (htmlContent) => {
        statusArea.classList.add('hidden');
        resultArea.innerHTML = htmlContent;
        resultArea.classList.remove('hidden');
    };

    const getVerdictClass = (verdict) => {
        if (!verdict) return 'verdict-malicious';
        const lowerVerdict = verdict.toLowerCase();
        const safeVerdicts = ['real', 'safe', 'not phishing', 'no audio track'];
        return safeVerdicts.some(v => lowerVerdict.includes(v)) ? 'verdict-safe' : 'verdict-malicious';
    };
    
    function formatExplanation(text) {
        if (!text) return '<p>No explanation available.</p>';
        return '<p>' + text.replace(/\*/g, '•').replace(/\n/g, '<br>') + '</p>';
    }

    // --- VIDEO ANALYSIS FORM ---
    document.getElementById('video-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const fileInput = document.getElementById('video-file-input');
        const urlInput = document.getElementById('video-url-input');
        const file = fileInput.files[0];
        const url = urlInput.value.trim();

        if (!file && !url) {
            showResult('<h3>Input Error</h3><p>Please select a video file or enter a URL.</p>');
            return;
        }
        
        if (file) {
            showVideoLoading();
            const formData = new FormData();
            formData.append('file', file);
            try {
                const uploadResponse = await fetch('/upload_video', { method: 'POST', body: formData });
                const uploadData = await uploadResponse.json();
                if (!uploadResponse.ok) throw new Error(uploadData.error || 'Video upload failed.');
                streamVideoAnalysis(uploadData.task_id, uploadData.filename, null);
            } catch (error) {
                showResult(`<h3>Operation Failed</h3><p>${error.message}</p>`);
            }
        } else {
            showLoading("Downloading video from URL...");
            try {
                const response = await fetch('/predict_video_from_url', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'Server error during URL processing.');
                showVideoLoading();
                streamVideoAnalysis(data.task_id, data.filename, url);
            } catch (error) {
                showResult(`<h3>Error</h3><p>${error.message}</p>`);
            }
        }
    });
    
    function streamVideoAnalysis(taskId, filename, url = null) {
        let streamUrl = `/stream_video_analysis/${taskId}?filename=${filename}`;
        if (url) {
            streamUrl += `&url=${encodeURIComponent(url)}`;
        }
        const eventSource = new EventSource(streamUrl);

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            switch (data.type) {
                case 'progress':
                    const progressBar = document.getElementById('progress-bar');
                    const progressPercentage = document.getElementById('progress-percentage');
                    const progressText = document.getElementById('progress-text');

                    // Handle detailed text messages from the server
                    if (data.message) {
                        if (progressText) progressText.textContent = data.message;
                    }

                    // Handle frame-by-frame progress bar
                    if (data.total && data.processed) {
                        const percentage = (data.processed / data.total) * 100;
                        if (progressBar) progressBar.style.width = `${percentage}%`;
                        if (progressPercentage) progressPercentage.textContent = `${percentage.toFixed(0)}%`;
                        // Overwrite generic message with specific frame progress
                        if (progressText) progressText.textContent = `Analyzing Frame ${data.processed} of ${data.total}`;
                    }
                    break;

                case 'result':
                    const resultHtml = `
                        <h3>Analysis Report</h3>
                        <div class="result-grid">
                            <div class="visual-container main-visual">
                                <h4>Annotated Frame</h4>
                                <img src="data:image/jpeg;base64,${data.result_image}" alt="Annotated video frame" class="result-image">
                            </div>
                            <div class="visual-container">
                                <h4>Visual Confidence Graph (Frame by Frame)</h4>
                                <div class="chart-container">
                                    <canvas id="confidenceChart"></canvas>
                                </div>
                            </div>
                            <div class="verdict-container">
                                <h4>Visual Verdict: <strong class="${getVerdictClass(data.verdict)}">${data.verdict}</strong></h4>
                                <p>Avg. Fake Confidence: ${(data.average_confidence * 100).toFixed(2)}%</p>
                                <div id="video-explanation-box" class="explanation-box"><div class="mini-spinner"></div><p>Generating AI explanation...</p></div>
                            </div>
                             <div class="verdict-container">
                                <h4>Audio Verdict: <strong class="${getVerdictClass(data.audio_verdict)}">${data.audio_verdict}</strong></h4>
                                <p>Confidence: ${(data.audio_confidence * 100).toFixed(2)}%</p>
                                <div id="audio-explanation-box" class="explanation-box"><div class="mini-spinner"></div><p>Generating AI explanation...</p></div>
                            </div>
                        </div>`;
                    showResult(resultHtml);

                    if (data.frame_scores && data.frame_scores.length > 0) {
                        const ctx = document.getElementById('confidenceChart').getContext('2d');
                        if (confidenceChart) confidenceChart.destroy();
                        confidenceChart = new Chart(ctx, {
                            type: 'line', data: { labels: data.frame_scores.map((_, i) => i + 1), datasets: [{ label: 'Fake Confidence', data: data.frame_scores.map(s => s * 100), borderColor: '#00ffff', backgroundColor: 'rgba(0, 255, 255, 0.1)', fill: true, tension: 0.2 }] },
                            options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, max: 100, ticks: { color: '#ccc' }, grid: { color: 'rgba(255,255,255,0.1)' } }, x: { ticks: { color: '#ccc' }, grid: { color: 'rgba(255,255,255,0.1)' } } }, plugins: { legend: { labels: { color: '#ccc' } } } }
                        });
                    }
                    break;
                case 'video_explanation':
                    const videoExpBox = document.getElementById('video-explanation-box');
                    if (videoExpBox) videoExpBox.innerHTML = formatExplanation(data.explanation);
                    break;
                case 'audio_explanation':
                    const audioExpBox = document.getElementById('audio-explanation-box');
                    if (audioExpBox) audioExpBox.innerHTML = formatExplanation(data.explanation);
                    eventSource.close();
                    break;
                case 'error':
                    showResult(`<h3>Analysis Error</h3><p>${data.message}</p>`);
                    eventSource.close();
                    break;
            }
        };
        eventSource.onerror = (e) => {
            showResult('<h3>Connection Error</h3><p>Failed to get analysis updates from the server.</p>');
            eventSource.close();
        };
    }

    
    // --- IMAGE ANALYSIS FORM ---
    document.getElementById('image-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const fileInput = document.getElementById('image-file-input');
        const urlInput = document.getElementById('image-url-input');
        const file = fileInput.files[0];
        const url = urlInput.value.trim();

        if (!file && !url) { 
            showResult('<h3>Input Error</h3><p>Please select an image file or enter a URL.</p>'); 
            return; 
        }
        
        let response;
        if (file) {
            showLoading("Analyzing image...");
            const formData = new FormData();
            formData.append('file', file);
            response = await fetch('/predict_image', { method: 'POST', body: formData });
        } else {
            showLoading("Downloading image from URL...");
            response = await fetch('/predict_image_from_url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            });
        }

        try {
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Server error during image analysis.');
            const verdictClass = getVerdictClass(data.verdict);
            const resultHtml = `
                <h3>Analysis Report</h3>
                <div class="result-grid-single">
                    <div class="visual-container">
                        <h4>Annotated Image</h4>
                        <img src="data:image/jpeg;base64,${data.result_image}" alt="Analyzed image" class="result-image">
                    </div>
                    <div class="verdict-container">
                        <h4>Verdict: <strong class="${verdictClass}">${data.verdict}</strong></h4>
                        <p>Fake Confidence: ${(data.average_confidence * 100).toFixed(2)}%</p>
                        <h4>AI Explanation:</h4>
                        <div class="explanation-box">${formatExplanation(data.explanation)}</div>
                    </div>
                </div>`;
            showResult(resultHtml);
        } catch (error) {
            showResult(`<h3>Error</h3><p>${error.message}</p>`);
        }
    });

    // --- AUDIO ANALYSIS FORM ---
    document.getElementById('audio-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const fileInput = document.getElementById('audio-file-input');
        const urlInput = document.getElementById('audio-url-input');
        const file = fileInput.files[0];
        const url = urlInput.value.trim();

        if (!file && !url) { 
            showResult('<h3>Input Error</h3><p>Please select an audio file or enter a URL.</p>'); 
            return; 
        }

        let response;
        if (file) {
            showLoading("Analyzing audio...");
            const formData = new FormData();
            formData.append('file', file);
            response = await fetch('/predict_audio', { method: 'POST', body: formData });
        } else {
            showLoading("Downloading and extracting audio from URL...");
            response = await fetch('/predict_audio_from_url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            });
        }
        
        try {
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Server error during audio analysis.');
            const verdictClass = getVerdictClass(data.verdict);
            const waveformHtml = data.waveform_image 
                ? `<div class="visual-container"><h4>Waveform</h4><img src="data:image/png;base64,${data.waveform_image}" alt="Audio waveform" class="result-image"></div>` 
                : '';
            
            const resultHtml = `
                <h3>Analysis Report</h3>
                <div class="result-grid-single">
                    ${waveformHtml}
                    <div class="verdict-container">
                        <h4>Verdict: <strong class="${verdictClass}">${data.verdict}</strong></h4>
                        <p>Confidence: ${(data.confidence * 100).toFixed(2)}%</p>
                        <h4>AI Explanation:</h4>
                        <div class="explanation-box">${formatExplanation(data.explanation)}</div>
                    </div>
                </div>`;
            showResult(resultHtml);
        } catch (error) {
            showResult(`<h3>Error</h3><p>${error.message}</p>`);
        }
    });
    
    // --- COMBINED ANALYSIS FORM ---
    document.getElementById('combined-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const emailText = document.getElementById('combined-input').value;
        const urlText = document.getElementById('url-input').value;
        if (!emailText && !urlText) { showResult('<h3>Input Error</h3><p>Please enter email text or a URL.</p>'); return; }
        showLoading("Performing combined scan...");

        try {
            const response = await fetch('/predict_combined', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: emailText, url: urlText })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Server error during combined analysis.');
            
            let urlResultsHtml = '';
            if(data.url_analysis && data.url_analysis.length > 0) {
                urlResultsHtml = `
                    <div class="result-section">
                        <h4>URL Scan Results (${data.urls_found} found)</h4>
                        ${data.url_analysis.map(item => `
                            <div class="url-item">
                                <div class="url-link" title="${item.url}">${item.url}</div>
                                <p><strong>Verdict:</strong> <span class="${getVerdictClass(item.verdict)}">${item.verdict}</span> | <strong>Risk Score:</strong> ${item.risk_score}%</p>
                                <div class="explanation-box">${formatExplanation(item.explanation)}</div>
                            </div>
                        `).join('')}
                    </div>`;
            }

            const resultHtml = `
                <h3>Analysis Report</h3>
                <div class="result-section">
                    <h4>Email Analysis</h4>
                    <p><strong>Verdict:</strong> <span class="${getVerdictClass(data.email_verdict)}">${data.email_verdict}</span></p>
                    <div class="explanation-box">${formatExplanation(data.email_explanation)}</div>
                </div>
                ${urlResultsHtml}`;
            showResult(resultHtml);
        } catch (error) {
            showResult(`<h3>Error</h3><p>${error.message}</p>`);
        }
    });
});