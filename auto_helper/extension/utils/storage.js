/**
 * Storage utility for the extension
 * Wrapper around chrome.storage.sync/local
 */

const Storage = {
    // Keys
    KEYS: {
        AUTO_MODE: 'auto_mode',
        LLM_CONFIG: 'llm_config',
        STATS: 'daily_stats',
        INTERACTED_VIDEOS: 'interacted_videos',
        SETTINGS: 'settings'
    },

    // Defaults
    DEFAULTS: {
        [ 'auto_mode' ]: true,
        [ 'llm_config' ]: {
            apiBaseUrl: 'http://localhost:11434/v1',
            apiKey: 'ollama',
            model: 'qwen2.5:3b'
        },
        [ 'daily_stats' ]: {
            date: new Date().toLocaleDateString(),
            analyzed: 0,
            interacted: 0,
            skipped: 0
        }
    },

    /**
     * Get value from storage
     * @param {string} key 
     * @returns {Promise<any>}
     */
    async get(key) {
        return new Promise((resolve) => {
            chrome.storage.sync.get([key], (result) => {
                if (result[key] === undefined && this.DEFAULTS[key] !== undefined) {
                    resolve(this.DEFAULTS[key]);
                } else {
                    resolve(result[key]);
                }
            });
        });
    },

    /**
     * Set value to storage
     * @param {string} key 
     * @param {any} value 
     * @returns {Promise<void>}
     */
    async set(key, value) {
        return new Promise((resolve) => {
            chrome.storage.sync.set({ [key]: value }, () => {
                resolve();
            });
        });
    },

    /**
     * Get multiple values
     * @param {string[]} keys 
     * @returns {Promise<object>}
     */
    async getMultiple(keys) {
        return new Promise((resolve) => {
            chrome.storage.sync.get(keys, (result) => {
                // Apply defaults
                const finalResult = { ...result };
                keys.forEach(key => {
                    if (finalResult[key] === undefined && this.DEFAULTS[key] !== undefined) {
                        finalResult[key] = this.DEFAULTS[key];
                    }
                });
                resolve(finalResult);
            });
        });
    }
};

// Export for module systems (if needed later)
if (typeof module !== 'undefined') {
    module.exports = Storage;
}
