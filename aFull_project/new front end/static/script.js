// This function handles switching between the tool tabs
function openTool(evt, toolName) {
    const toolContent = document.getElementsByClassName("tool-content");
    for (let i = 0; i < toolContent.length; i++) {
        toolContent[i].style.display = "none";
    }

    const tabLinks = document.getElementsByClassName("tab-link");
    for (let i = 0; i < tabLinks.length; i++) {
        tabLinks[i].className = tabLinks[i].className.replace(" active", "");
    }

    const currentTool = document.getElementById(toolName);
    if (currentTool) {
        currentTool.style.display = "block";
    }
    if (evt && evt.currentTarget) {
        evt.currentTarget.className += " active";
    }
}

// This function runs after the whole page has loaded
document.addEventListener('DOMContentLoaded', () => {
    const videoForm = document.getElementById('video-form');
    const audioForm = document.getElementById('audio-form');
    const urlForm = document.getElementById('url-form');
    const emailForm = document.getElementById('email-form');
    const resultArea = document.getElementById('result-area');
    const resultContent = document.getElementById('result-content');

    const handleFormSubmit = (form, url) => {
        if (!form) return; // Safety check
        
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            if(resultArea) resultArea.classList.remove('hidden');
            if(resultContent) resultContent.innerHTML = '<p>Analyzing, please wait...</p>';

            try {
                const formData = new FormData(form);
                const response = await fetch(url, { method: 'POST', body: formData });
                const result = await response.json();

                if (response.ok) {
                    let html = `<strong>Verdict:</strong> <span class="verdict">${result.verdict}</span><br>`;
                    if (result.confidence) html += `<strong>Confidence:</strong> ${(result.confidence * 100).toFixed(2)}%`;
                    if (result.fake_confidence) html += `<strong>Fake Confidence:</strong> ${(result.fake_confidence * 100).toFixed(2)}%`;
                    if (result.risk_score) html += `<strong>Risk Score:</strong> ${result.risk_score}`;
                    if(resultContent) resultContent.innerHTML = html;
                } else {
                    if(resultContent) resultContent.innerHTML = `<p class="error">Error: ${result.error || 'Unknown error'}</p>`;
                }
            } catch (error) {
                if(resultContent) resultContent.innerHTML = `<p class="error">An unexpected network error occurred.</p>`;
            }
        });
    };

    handleFormSubmit(videoForm, '/predict_video');
    handleFormSubmit(audioForm, '/predict_audio');
    handleFormSubmit(urlForm, '/predict_url');
    handleFormSubmit(emailForm, '/predict_email');
    
    const defaultTab = document.querySelector('.tab-link');
    if (defaultTab) {
        defaultTab.click();
    }
});