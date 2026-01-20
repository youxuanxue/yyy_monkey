document.addEventListener('DOMContentLoaded', async () => {
    // Elements
    const el = {
        apiBaseUrl: document.getElementById('apiBaseUrl'),
        apiKey: document.getElementById('apiKey'),
        model: document.getElementById('model'),
        systemPrompt: document.getElementById('systemPrompt'),
        skipInteracted: document.getElementById('skipInteracted'),
        maxDailyInteractions: document.getElementById('maxDailyInteractions'),
        saveBtn: document.getElementById('saveBtn'),
        testConnectionBtn: document.getElementById('testConnectionBtn'),
        saveStatus: document.getElementById('saveStatus'),
        connectionStatus: document.getElementById('connectionStatus')
    };

    // Initialize
    await loadSettings();

    // Events
    el.saveBtn.addEventListener('click', saveSettings);
    el.testConnectionBtn.addEventListener('click', testConnection);

    /**
     * Load settings from storage
     */
    async function loadSettings() {
        const llmConfig = await Storage.get(Storage.KEYS.LLM_CONFIG);
        const settings = await Storage.get(Storage.KEYS.SETTINGS) || {};

        // LLM Config
        el.apiBaseUrl.value = llmConfig.apiBaseUrl || '';
        el.apiKey.value = llmConfig.apiKey || '';
        el.model.value = llmConfig.model || '';

        // General Settings
        // Load default systemPrompt from config file if not set
        if (!settings.systemPrompt) {
            try {
                const url = chrome.runtime.getURL('config/llm_prompt.json');
                const res = await fetch(url);
                const promptConfig = await res.json();
                el.systemPrompt.value = promptConfig.task_interaction_decision.default.system_prompt;
            } catch (e) {
                console.error('Failed to load default prompt config:', e);
                el.systemPrompt.value = '';
            }
        } else {
            el.systemPrompt.value = settings.systemPrompt;
        }
        el.skipInteracted.checked = settings.skipInteracted !== false; // Default true
        el.maxDailyInteractions.value = settings.maxDailyInteractions || 50;
    }

    /**
     * Save settings to storage
     */
    async function saveSettings() {
        el.saveStatus.textContent = '保存中...';
        
        const llmConfig = {
            apiBaseUrl: el.apiBaseUrl.value.trim(),
            apiKey: el.apiKey.value.trim(),
            model: el.model.value.trim()
        };

        const settings = {
            systemPrompt: el.systemPrompt.value.trim(),
            skipInteracted: el.skipInteracted.checked,
            maxDailyInteractions: parseInt(el.maxDailyInteractions.value)
        };

        await Storage.set(Storage.KEYS.LLM_CONFIG, llmConfig);
        await Storage.set(Storage.KEYS.SETTINGS, settings);

        el.saveStatus.textContent = '设置已保存';
        setTimeout(() => {
            el.saveStatus.textContent = '';
        }, 2000);
    }

    /**
     * Test LLM Connection
     */
    async function testConnection() {
        el.connectionStatus.textContent = '连接中...';
        el.connectionStatus.className = 'status-text';
        
        const config = {
            apiBaseUrl: el.apiBaseUrl.value.trim(),
            apiKey: el.apiKey.value.trim(),
            model: el.model.value.trim()
        };

        try {
            // Send check request to background (or check directly if possible)
            // Using direct fetch here for simplicity as we are in extension context
            // But background is better for CORS usually. 
            // Let's try sending message to background.
            
            const response = await new Promise((resolve) => {
                chrome.runtime.sendMessage({ 
                    type: 'CHECK_LLM', 
                    payload: config 
                }, resolve);
            });

            if (response && response.success) {
                el.connectionStatus.textContent = '✅ 连接成功';
                el.connectionStatus.style.color = 'green';
            } else {
                el.connectionStatus.textContent = '❌ 连接失败: ' + (response?.error || '未知错误');
                el.connectionStatus.style.color = 'red';
            }

        } catch (error) {
            el.connectionStatus.textContent = '❌ 错误: ' + error.message;
            el.connectionStatus.style.color = 'red';
        }
    }
});
