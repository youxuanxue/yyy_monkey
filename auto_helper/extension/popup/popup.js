document.addEventListener('DOMContentLoaded', async () => {
    // Elements
    const autoModeToggle = document.getElementById('autoModeToggle');
    const autoModeStatus = document.getElementById('autoModeStatus');
    const llmModelElement = document.getElementById('llmModel');
    const llmStatusElement = document.getElementById('llmConnectionStatus');
    const statsAnalyzed = document.getElementById('statsAnalyzed');
    const statsInteracted = document.getElementById('statsInteracted');
    const statsSkipped = document.getElementById('statsSkipped');
    const openSettingsBtn = document.getElementById('openSettings');

    // Initialize UI
    await initUI();

    // Event Listeners
    autoModeToggle.addEventListener('change', handleAutoModeChange);
    openSettingsBtn.addEventListener('click', openSettings);

    /**
     * Initialize UI with stored values
     */
    async function initUI() {
        // Load Auto Mode
        const isAutoMode = await Storage.get(Storage.KEYS.AUTO_MODE);
        updateAutoModeUI(isAutoMode);

        // Load LLM Config
        const llmConfig = await Storage.get(Storage.KEYS.LLM_CONFIG);
        llmModelElement.textContent = llmConfig.model || 'Unknown';
        
        // Check LLM Connection (Simple simulation for now, real check would involve API call)
        checkLLMConnection(llmConfig);

        // Load Stats
        loadStats();
    }

    /**
     * Update Auto Mode UI state
     * @param {boolean} isEnabled 
     */
    function updateAutoModeUI(isEnabled) {
        autoModeToggle.checked = isEnabled;
        autoModeStatus.textContent = isEnabled ? '已开启' : '已关闭';
        autoModeStatus.style.color = isEnabled ? 'var(--success-color)' : 'var(--text-secondary)';
    }

    /**
     * Handle Auto Mode Toggle Change
     */
    async function handleAutoModeChange(e) {
        const isEnabled = e.target.checked;
        updateAutoModeUI(isEnabled);
        await Storage.set(Storage.KEYS.AUTO_MODE, isEnabled);
        
        // Notify Content Script / Background (Optional, if needed immediately)
        // chrome.runtime.sendMessage({ type: 'AUTO_MODE_CHANGED', value: isEnabled });
    }

    /**
     * Load and display stats
     */
    async function loadStats() {
        const stats = await Storage.get(Storage.KEYS.STATS);
        
        // Reset if new day (basic logic)
        const today = new Date().toLocaleDateString();
        if (stats.date !== today) {
            stats.date = today;
            stats.analyzed = 0;
            stats.interacted = 0;
            stats.skipped = 0;
            await Storage.set(Storage.KEYS.STATS, stats);
        }

        statsAnalyzed.textContent = stats.analyzed;
        statsInteracted.textContent = stats.interacted;
        statsSkipped.textContent = stats.skipped;
    }

    /**
     * Check LLM Connection Status
     * @param {object} config 
     */
    async function checkLLMConnection(config) {
        // Update UI to loading
        llmStatusElement.className = 'status-indicator';
        llmStatusElement.querySelector('.dot').style.backgroundColor = 'var(--neutral-color)';
        llmStatusElement.querySelector('.text').textContent = '检查中...';

        try {
            // Send message to background script to check connection
            // For now, we'll try to fetch directly if permissions allow, or default to message
            
            // Note: In a real extension, we might send a message to background service worker
            // chrome.runtime.sendMessage({ type: 'CHECK_LLM_CONNECTION' }, (response) => { ... });
            
            // Simulating a check for now since we don't have the full background logic yet
            // Assuming default local ollama is up
            
            const isConnected = true; // Placeholder for actual check logic
            
            if (isConnected) {
                llmStatusElement.className = 'status-indicator connected';
                llmStatusElement.querySelector('.text').textContent = '已连接';
            } else {
                throw new Error('Connection failed');
            }
        } catch (error) {
            llmStatusElement.className = 'status-indicator disconnected';
            llmStatusElement.querySelector('.text').textContent = '连接失败';
        }
    }

    /**
     * Open Options Page
     */
    function openSettings() {
        if (chrome.runtime.openOptionsPage) {
            chrome.runtime.openOptionsPage();
        } else {
            window.open(chrome.runtime.getURL('options/options.html'));
        }
    }
});
