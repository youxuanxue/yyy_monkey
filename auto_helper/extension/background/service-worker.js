// Service Worker
importScripts('../utils/messaging.js');
importScripts('../utils/storage.js');
importScripts('llm-client.js');

console.log('[Background] Service Worker Loaded');

// Global Instances
let llmClient = null;
let promptConfig = null;

// Initialize
async function init() {
    const config = await Storage.get(Storage.KEYS.LLM_CONFIG);
    llmClient = new LLMClient(config);
    
    try {
        const url = chrome.runtime.getURL('config/llm_prompt.json');
        const res = await fetch(url);
        promptConfig = await res.json();
    } catch (e) {
        console.error('Failed to load prompt config:', e);
        promptConfig = {
            task_interaction_decision: {
                default: {
                    system_prompt: "You are a YouTube Shorts helper. Return JSON with should_interact (bool), actions (obj), comment_text (string)."
                }
            }
        };
    }
}

init();

// Listen for messages
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    const { type, payload } = message;

    if (type === MESSAGE_TYPES.VIDEO_CHANGED) {
        console.log('[Background] Received VIDEO_CHANGED from tab', sender.tab?.id, payload);
        handleVideoChange(payload, sender.tab?.id);
    } else if (type === MESSAGE_TYPES.CHECK_LLM) {
        checkLLM(payload).then(sendResponse);
        return true; 
    }
});

async function handleVideoChange(data, tabId) {
    console.log('[Background] Video changed:', data.videoId);
    
    // Notify Content to show status
    Messaging.sendToActiveTab(MESSAGE_TYPES.SHOW_DECISION, { status: 'analyzing', message: '正在分析...' });

    // 1. Check Auto Mode
    const isAuto = await Storage.get(Storage.KEYS.AUTO_MODE);
    if (!isAuto) {
        Messaging.sendToActiveTab(MESSAGE_TYPES.SHOW_DECISION, { status: 'info', message: '自动模式已关闭' });
        return;
    }

    // Load Settings
    const settings = await Storage.get(Storage.KEYS.SETTINGS) || {};
    
    // 2. Safety Checks
    if (settings.skipInteracted !== false) {
        const interactedVideos = await Storage.get(Storage.KEYS.INTERACTED_VIDEOS) || [];
        if (interactedVideos.includes(data.videoId)) {
            Messaging.sendToActiveTab(MESSAGE_TYPES.SHOW_DECISION, { status: 'skip', message: '已互动过' });
            // Content script will auto-swipe based on the skip message
            return;
        }
    }

    const stats = await Storage.get(Storage.KEYS.STATS);
    const today = new Date().toLocaleDateString();
    if (stats.date !== today) {
        stats.date = today;
        stats.analyzed = 0;
        stats.interacted = 0;
        stats.skipped = 0;
        await Storage.set(Storage.KEYS.STATS, stats);
    }

    const maxInteractions = settings.maxDailyInteractions || 50;
    if (stats.interacted >= maxInteractions) {
        Messaging.sendToActiveTab(MESSAGE_TYPES.SHOW_DECISION, { status: 'skip', message: '今日达限' });
        // Content script will auto-swipe based on the skip message
        return;
    }

    // 3. Analyze with LLM
    if (llmClient && promptConfig) {
        // Use custom systemPrompt from settings, or fallback to default from config file
        let systemPrompt = settings.systemPrompt || promptConfig.task_interaction_decision.default.system_prompt;

        const decision = await llmClient.analyzeVideo(data.info, systemPrompt);
        console.log('[Background] LLM Decision:', decision);

        if (decision.success) {
             if (decision.result.should_interact) {

                // Show success status
                Messaging.sendToActiveTab(MESSAGE_TYPES.SHOW_DECISION, { 
                    status: 'success', 
                    message: '即将互动',
                    details: `理由: ${decision.result.reason || '符合兴趣'}`
                });

                // Normalize actions (fix LLM return format issues)
                let actions = decision.result.actions;
                if (typeof actions === 'string') {
                    const act = {};
                    if (actions.includes('subscribe')) act.subscribe = true;
                    if (actions.includes('like')) act.like = true;
                    if (actions.includes('comment')) act.comment = true;
                    actions = act;
                } else if (Array.isArray(actions)) {
                    // Handle array format ["like", "comment"]
                    const act = {};
                    if (actions.includes('subscribe')) act.subscribe = true;
                    if (actions.includes('like')) act.like = true;
                    if (actions.includes('comment')) act.comment = true;
                    actions = act;
                }

                // 4. Send Interaction Command
                // Content script will auto-swipe after all actions are completed
                setTimeout(() => {
                    Messaging.sendToActiveTab(MESSAGE_TYPES.EXECUTE_INTERACTION, {
                        actions: actions,
                        comment: decision.result.comment_text
                    });
                }, 2000);
                
                await recordInteraction(data.videoId);
                updateStats(true, false);
            } else {
                updateStats(true, true);
                Messaging.sendToActiveTab(MESSAGE_TYPES.SHOW_DECISION, { 
                    status: 'skip', 
                    message: '不感兴趣',
                    details: decision.result.reason
                });
                // Content script will auto-swipe based on the skip message
            }
        } else {
            Messaging.sendToActiveTab(MESSAGE_TYPES.SHOW_DECISION, { status: 'error', message: '分析失败' });
        }
    }
}

async function recordInteraction(videoId) {
    const interactedVideos = await Storage.get(Storage.KEYS.INTERACTED_VIDEOS) || [];
    if (!interactedVideos.includes(videoId)) {
        interactedVideos.push(videoId);
        if (interactedVideos.length > 1000) {
            interactedVideos.shift();
        }
        await Storage.set(Storage.KEYS.INTERACTED_VIDEOS, interactedVideos);
    }
}

async function updateStats(analyzed = false, skipped = false) {
    const stats = await Storage.get(Storage.KEYS.STATS);
    if (analyzed) stats.analyzed++;
    if (skipped) stats.skipped++;
    else if (analyzed && !skipped) stats.interacted++;
    await Storage.set(Storage.KEYS.STATS, stats);
}

async function checkLLM(config) {
    try {
        // 1. Try standard OpenAI /models endpoint (works for Ollama /v1/models too)
        // Remove trailing slash if present
        const baseUrl = config.apiBaseUrl.replace(/\/$/, '');
        
        let response = await fetch(`${baseUrl}/models`);
        
        // If /models works, we are good
        if (response.ok) {
            return { success: true };
        }

        // 2. If /models fails (404), try chat completion as fallback
        response = await fetch(`${baseUrl}/chat/completions`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${config.apiKey}`
            },
            body: JSON.stringify({
                model: config.model,
                messages: [{ role: 'user', content: 'hi' }],
                max_tokens: 1
            })
        });

        if (response.ok) {
            return { success: true };
        }
        
        // 3. Handle specific errors
        if (response.status === 403) {
            return { success: false, error: 'CORS限制: 请设置 OLLAMA_ORIGINS="*"' };
        }
        
        return { success: false, error: `HTTP ${response.status}` };
    } catch (e) {
        return { success: false, error: e.message };
    }
}
