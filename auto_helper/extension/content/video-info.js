/**
 * Video Information Extraction
 * Depends on SELECTORS from utils/selectors.js
 */

const VideoInfoExtractor = {
    /**
     * Extract all video info
     * @returns {Promise<object>}
     */
    async extract() {
        // Wait a bit for DOM to settle if needed, or retry
        return this.retryExtraction();
    },

    async retryExtraction(retries = 5, delay = 500) {
        for (let i = 0; i < retries; i++) {
            const info = this._getRawInfo();
            if (this._isValid(info)) {
                return info;
            }
            await new Promise(r => setTimeout(r, delay));
        }
        return this._getRawInfo(); // Return whatever we have
    },

    _getRawInfo() {
        return {
            title: this._getText(SELECTORS.videoInfo.title),
            channelName: this._getText(SELECTORS.videoInfo.channelName),
            url: window.location.href,
            timestamp: Date.now()
        };
    },

    _getText(selectors) {
        if (!Array.isArray(selectors)) {
            selectors = [selectors];
        }

        for (const selector of selectors) {
            const elements = document.querySelectorAll(selector);
            for (const el of elements) {
                if (el && el.innerText && el.innerText.trim().length > 0) {
                    return el.innerText.trim().replace(/[\r\n]+/g, ' ');
                }
            }
        }
        return "";
    },

    _isValid(info) {
        // At minimum we need a title
        return info.title.length > 0;
    }
};
