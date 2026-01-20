/**
 * Messaging types and helpers
 */

const MESSAGE_TYPES = {
    // Content -> Background
    VIDEO_CHANGED: 'VIDEO_CHANGED',
    
    // Background -> Content
    EXECUTE_INTERACTION: 'EXECUTE_INTERACTION',
    SHOW_DECISION: 'SHOW_DECISION',
    
    // Popup -> Background
    CHECK_LLM: 'CHECK_LLM',
    GET_STATS: 'GET_STATS'
};

const Messaging = {
    /**
     * Send message to Background script
     * @param {string} type 
     * @param {any} payload 
     * @returns {Promise<any>}
     */
    sendToBackground(type, payload = {}) {
        return new Promise((resolve, reject) => {
            try {
                chrome.runtime.sendMessage({ type, payload }, (response) => {
                    if (chrome.runtime.lastError) {
                        console.warn('Messaging error:', chrome.runtime.lastError);
                        // Don't reject, just resolve null to avoid breaking flow
                        resolve(null);
                    } else {
                        resolve(response);
                    }
                });
            } catch (e) {
                console.error('Send message failed:', e);
                resolve(null);
            }
        });
    },

    /**
     * Send message to Content Script (active tab)
     * @param {string} type 
     * @param {any} payload 
     * @returns {Promise<any>}
     */
    async sendToActiveTab(type, payload = {}) {
        return new Promise((resolve) => {
            chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
                if (tabs.length === 0) {
                    resolve(null);
                    return;
                }
                chrome.tabs.sendMessage(tabs[0].id, { type, payload }, (response) => {
                     if (chrome.runtime.lastError) {
                        resolve(null);
                    } else {
                        resolve(response);
                    }
                });
            });
        });
    }
};

// Export
if (typeof module !== 'undefined') {
    module.exports = { MESSAGE_TYPES, Messaging };
}
