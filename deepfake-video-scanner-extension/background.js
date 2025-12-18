async function readStream(stream, onData) {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) {
            // Process any remaining data in the buffer
            if (buffer.startsWith('data: ')) {
                try {
                    const json = JSON.parse(buffer.substring(6));
                    onData(json);
                } catch (e) {
                    console.error('Error parsing final stream data:', e, 'Buffer:', buffer);
                }
            }
            break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // Keep the last, possibly incomplete, line

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

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'initiateScan') {
        const url = request.url;
        const initialState = { status: 'scanning', url: url, progress: { message: 'Initiating scan...' } };

        chrome.storage.local.set({ scanState: initialState }, async () => {
            try {
                const response = await fetch('http://127.0.0.1:5000/ext/predict_video_extension', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url }),
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                await readStream(response.body, (event) => {
                    if (event.type === 'progress') {
                        // MAP backend fields to frontend fields
                        const progressData = {
                            current: event.processed,
                            total: event.total,
                            message: event.status
                        };
                        
                        // Validate progress data before setting it
                        if (progressData.total > 0 && isFinite(progressData.current) && isFinite(progressData.total)) {
                            const progressState = { status: 'scanning', url: url, progress: progressData };
                            chrome.storage.local.set({ scanState: progressState });
                        }
                    } else if (event.type === 'final_result') {
                        const finalState = { status: 'complete', url: url, result: event.data };
                        console.log('Scan complete. Final verdict:', finalState.result); // Log the verdict
                        chrome.storage.local.set({ scanState: finalState });
                    } else if (event.type === 'explanations_ready') {
                        chrome.storage.local.get('scanState', (data) => {
                            if (data.scanState && data.scanState.status === 'complete') {
                                const updatedState = data.scanState;
                                updatedState.result.video_explanation = event.data.video_explanation;
                                updatedState.result.audio_explanation = event.data.audio_explanation;
                                chrome.storage.local.set({ scanState: updatedState });
                            }
                        });
                    } else if (event.type === 'error') {
                        throw new Error(event.message);
                    }
                });

            } catch (error) {
                console.error('Error during scan stream:', error);
                const errorResult = {
                    video_prediction: 'Error',
                    video_explanation: `An error occurred: ${error.message}`,
                    audio_prediction: 'Error',
                    audio_explanation: 'Please check the server logs for more details.'
                };
                const errorState = { status: 'complete', result: errorResult, url: url };
                chrome.storage.local.set({ scanState: errorState });
            }
        });

        sendResponse({ status: 'Scan stream initiated' });
    }
    return true; // Indicate async response
});