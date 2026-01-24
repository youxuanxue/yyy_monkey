// Content Script
console.log('[Content] Shorts Helper Loaded');

// State
let currentVideoId = null;

// Initialize
function init() {
    console.log('[Content] Initializing...');
    UIOverlay.init();
    setupNavigationListener();
    setupMessageListener();
    
    // Check initial URL
    handleUrlChange();
}

function setupMessageListener() {
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        const { type, payload } = message;
        if (type === MESSAGE_TYPES.EXECUTE_INTERACTION) {
            console.log('[Content] Received Interaction Order:', payload);
            Interactor.perform(payload.actions, payload.comment, payload.skipType);
        } else if (type === MESSAGE_TYPES.SHOW_DECISION) {
            console.log('[Content] Show Decision:', payload);
            handleShowDecision(payload);
        }
    });
}

function handleShowDecision(payload) {
    let type = 'info';
    if (payload.status === 'analyzing') type = 'processing';
    if (payload.status === 'success') type = 'success';
    if (payload.status === 'skip') type = 'skip';
    if (payload.status === 'error') type = 'error';

    UIOverlay.show(payload.message, payload.details, type);
    
    // Auto-swipe for skip cases
    if (payload.status === 'skip') {
        let skipType = null;
        if (payload.message === '已互动过') {
            skipType = 'alreadyInteracted';
        } else if (payload.message === '今日达限') {
            skipType = 'dailyLimit';
        } else if (payload.message === '不感兴趣') {
            skipType = 'notInterested';
        }
        
        if (skipType) {
            console.log(`[Content] Auto-swipe for skip case: ${skipType}`);
            Interactor.perform({ swipe: true }, null, skipType);
        }
    }
}

function setupNavigationListener() {
    window.addEventListener('popstate', handleUrlChange);
    
    let lastUrl = location.href;
    setInterval(() => {
        const url = location.href;
        if (url !== lastUrl) {
            lastUrl = url;
            handleUrlChange();
        }
    }, 1000);
}

async function handleUrlChange() {
    const url = location.href;
    if (url.includes('/shorts/')) {
        const videoId = extractVideoId(url);
        
        if (videoId && videoId !== currentVideoId) {
            currentVideoId = videoId;
            console.log('[Content] New Short detected:', videoId);
            
            // Clear previous overlay status
            UIOverlay.hide();
            
            setTimeout(processNewVideo, 1500); 
        }
    }
}

function extractVideoId(url) {
    try {
        return url.split('/shorts/')[1].split('?')[0];
    } catch (e) {
        return null;
    }
}

async function processNewVideo() {
    console.log('[Content] Processing video...');
    
    // Extract Info
    const info = await VideoInfoExtractor.extract();
    console.log('[Content] Extracted Info:', info);

    // Send to background for analysis
    if (info.title) {
        Messaging.sendToBackground(MESSAGE_TYPES.VIDEO_CHANGED, {
            videoId: currentVideoId,
            info: info
        });
    } else {
        console.warn('[Content] Failed to extract video info');
    }
}

// Start
setTimeout(init, 500);
