let mediaRecorder;
let data = [];

chrome.runtime.onMessage.addListener(async (message) => {
  if (message.target === 'offscreen' && message.type === 'start-offscreen-recording') {
    data = [];

    const stream = await navigator.mediaDevices.getUserMedia({
      video: { mandatory: { chromeMediaSource: 'tab', chromeMediaSourceId: message.streamId } },
      audio: { mandatory: { chromeMediaSource: 'tab', chromeMediaSourceId: message.streamId } },
    });
    
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'video/webm; codecs=vp9' });

    mediaRecorder.ondataavailable = (event) => data.push(event.data);
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach(track => track.stop());
      const blob = new Blob(data, { type: 'video/webm' });

      // Convert Blob to Base64 dataURL to send it via chrome.runtime.sendMessage
      const reader = new FileReader();
      reader.onloadend = () => {
        // Send the base64 string to the background script
        chrome.runtime.sendMessage({ type: 'upload-video', dataUrl: reader.result });
      };
      reader.readAsDataURL(blob);
    };

    mediaRecorder.start();
    
    setTimeout(() => {
      if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
      }
    }, message.duration);
  }
});