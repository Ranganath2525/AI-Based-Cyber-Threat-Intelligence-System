(function() {
    const videos = document.querySelectorAll('video');
    let videoSrc = null;

    if (videos.length > 0) {
        for (let video of videos) {
            if (video.src) {
                videoSrc = video.src;
                break;
            }
            const sourceElement = video.querySelector('source');
            if (sourceElement && sourceElement.src) {
                videoSrc = sourceElement.src;
                break;
            }
        }
    }
    
    if (videoSrc) {
        const absoluteUrl = new URL(videoSrc, window.location.href).href;
        chrome.runtime.sendMessage({ action: "videoUrlFound", url: absoluteUrl });
    } else {
        chrome.runtime.sendMessage({ action: "videoUrlNotFound" });
    }
})();