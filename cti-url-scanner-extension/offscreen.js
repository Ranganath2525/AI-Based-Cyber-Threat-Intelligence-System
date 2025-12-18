chrome.runtime.onMessage.addListener((message) => {
  if (message.target === 'offscreen' && message.type === 'start-offscreen-recording') {
    handleRecording(message);
  }
  return false; // Explicitly return false to avoid async response error
});

async function handleRecording(message) {
  let mediaRecorder;
  let data = [];

  const stream = await navigator.mediaDevices.getUserMedia({
    video: { mandatory: { chromeMediaSource: 'tab', chromeMediaSourceId: message.streamId } },
    audio: { mandatory: { chromeMediaSource: 'tab', chromeMediaSourceId: message.streamId } },
  });

  // Create an audio element to play back the captured audio in real-time.
  const output = new Audio();
  output.srcObject = stream;
  output.play();
  
  mediaRecorder = new MediaRecorder(stream, { mimeType: 'video/webm; codecs=vp9' });

  mediaRecorder.ondataavailable = (event) => data.push(event.data);
  mediaRecorder.onstop = () => {
    stream.getTracks().forEach(track => track.stop());
    const blob = new Blob(data, { type: 'video/webm' });

    const reader = new FileReader();
    reader.onloadend = () => {
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