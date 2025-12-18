
console.log("Email Observer script loaded.");

// --- CONFIGURATION ---
const GMAIL_SELECTORS = {
    emailContainer: '.nH.hx', // The container for open emails
    emailBody: '.a3s.aiL, .ii.gt' // The actual body of the email
};

const OUTLOOK_SELECTORS = {
    emailContainer: 'div[aria-label="Message body"]', // The container for the message body
    emailBody: 'div[aria-label="Message body"]'
};

const SCAN_DEBOUNCE_MS = 2000; // Wait 2 seconds after the last change before scanning

// --- STATE ---
let currentEmailBody = null;
let debounceTimer;

// --- CORE LOGIC ---

/**
 * Determines which email client is active and starts the appropriate observer.
 */
function initializeObserver() {
    const { host } = window.location;
    if (host.includes("mail.google.com")) {
        console.log("Gmail detected. Starting observer.");
        observe(GMAIL_SELECTORS);
    } else if (host.includes("outlook.live.com")) {
        console.log("Outlook detected. Starting observer.");
        observe(OUTLOOK_SELECTORS);
    }
}

/**
 * Sets up a MutationObserver to watch for changes in the email client's UI.
 * @param {object} selectors - The CSS selectors for the active email client.
 */
function observe(selectors) {
    const observer = new MutationObserver(mutations => {
        const emailContainer = document.querySelector(selectors.emailContainer);
        if (emailContainer) {
            // Check if the email body has changed
            const newEmailBody = emailContainer.querySelector(selectors.emailBody);
            if (newEmailBody && newEmailBody !== currentEmailBody) {
                currentEmailBody = newEmailBody;
                // Debounce to avoid multiple scans for the same email
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    console.log("New email detected. Triggering scan.");
                    triggerScan(currentEmailBody);
                }, SCAN_DEBOUNCE_MS);
            }
        }
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
}

/**
 * Extracts content and sends a message to the background script to start a scan.
 * @param {HTMLElement} emailBodyEl - The HTML element containing the email body.
 */
function triggerScan(emailBodyEl) {
    if (!emailBodyEl) return;

    const email_text = emailBodyEl.innerText;
    const urls = Array.from(emailBodyEl.querySelectorAll('a[href]')).map(a => a.href);

    if (email_text || urls.length > 0) {
        console.log(`Sending auto_scan_email message for ${urls.length} URLs.`);
        chrome.runtime.sendMessage({
            action: "auto_scan_email",
            email_text: email_text,
            urls: urls
        }, response => {
            if (chrome.runtime.lastError) {
                console.error("Error sending message:", chrome.runtime.lastError);
            } else {
                console.log("Auto-scan message sent, response:", response);
            }
        });
    }
}

// --- INITIALIZATION ---
initializeObserver();
