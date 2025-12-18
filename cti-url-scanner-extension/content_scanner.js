if (typeof window.ctiScannerLoaded === 'undefined') {
    window.ctiScannerLoaded = true;

    console.log("CTI Content Scanner Initializing (v5 - Robust Observer).");

    const emailBodySelectors = ['.a3s.aiL', '.ii.gt', '.WordSection1', 'div[aria-label="Message body"]'];
    let observer = null; // Declare observer in a shared scope

    // --- Core Scanning Logic for Both Manual and Automatic Scans ---
    function scanEmailBody(emailBodyNode, isManual = false) {
        if (!emailBodyNode) {
            return;
        }
        if (emailBodyNode.dataset.ctiScanned === 'true') {
            return;
        }
        emailBodyNode.dataset.ctiScanned = 'true';

        console.log(`CTI Scanner: Starting ${isManual ? 'manual' : 'automatic'} scan...`);

        const emailText = emailBodyNode.innerText;
        const linkElements = emailBodyNode.querySelectorAll('a[href]');
        const urlsToScan = Array.from(linkElements).map(link => link.href);

        if (!emailText && urlsToScan.length === 0) {
            return;
        }

        try {
            chrome.runtime.sendMessage({ 
                action: 'scan_links',
                email_text: emailText,
                urls: urlsToScan
            });
        } catch (e) {
            if (e.message.includes('Extension context invalidated')) {
                console.error("CTI Scanner: Context invalidated. Shutting down observer.");
                if (observer) {
                    observer.disconnect(); // Disconnect the old observer
                }
            } else {
                throw e;
            }
        }
    }

    // --- Listener for Manual Scan Requests from the Popup ---
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.action === "scan_links") {
            console.log("CTI Scanner: Received manual scan request from popup.");
            let emailBody = null;
            for (const selector of emailBodySelectors) {
                const elements = document.querySelectorAll(selector);
                if (elements.length > 0) {
                    emailBody = elements[elements.length - 1];
                }
            }

            if (emailBody) {
                const emailText = emailBody.innerText;
                const urls = Array.from(emailBody.querySelectorAll('a[href]')).map(a => a.href);
                
                console.log(`CTI Scanner: Extracted ${urls.length} links for manual scan.`);
                
                sendResponse({
                    status: 'data_extracted',
                    data: {
                        emailText: emailText,
                        urls: urls
                    }
                });
            } else {
                sendResponse({
                    status: 'error',
                    message: 'Could not find a readable email body on the page.'
                });
            }
            return true;
        }
    });

    // --- Automatic Scanner using MutationObserver ---
    function startObserver() {
        const targetNode = document.body;
        if (!targetNode) {
            return;
        }

        // Assign to the observer variable in the shared scope
        observer = new MutationObserver((mutationsList, obs) => {
            for (const mutation of mutationsList) {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    for (const node of mutation.addedNodes) {
                        if (node.nodeType === Node.ELEMENT_NODE) {
                            for (const selector of emailBodySelectors) {
                                const emailBody = node.matches(selector) ? node : node.querySelector(selector);
                                if (emailBody) {
                                    setTimeout(() => scanEmailBody(emailBody, false), 500);
                                    return;
                                }
                            }
                        }
                    }
                }
            }
        });

        console.log("CTI Scanner: MutationObserver is now watching for new emails.");
        observer.observe(targetNode, { childList: true, subtree: true });
    }

    setTimeout(startObserver, 2000);

} else {
    console.log("CTI Content Scanner already loaded. Skipping initialization.");
}