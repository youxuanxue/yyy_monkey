/**
 * Selectors for YouTube Shorts elements
 */
const SELECTORS = {
    // Info extraction
    videoInfo: {
        // Multiple strategies for robustness
        title: [
            // YouTube Shorts 2026 structure - updated from user snippets
            'ytd-reel-video-renderer[is-active] .ytReelMultiFormatLinkViewModelTitle span',
            'ytd-reel-video-renderer[is-active] .ytReelMultiFormatLinkViewModelTitle',
            'ytd-reel-video-renderer[is-active] yt-shorts-video-title-view-model span',
            
            // Previous strategies
            'ytd-reel-video-renderer[is-active] .yt-core-attributed-string--link-inherit-color',
            'ytd-reel-video-renderer[is-active] #title span',
            'ytd-reel-video-renderer[is-active] #title',
            '#shorts-player h2.title',
            'yt-formatted-string.ytd-reel-video-renderer'
        ],
        channelName: [
            // YouTube Shorts 2026 structure - updated from user snippets
            'ytd-reel-video-renderer[is-active] .yt-core-attributed-string__link--call-to-action-color[href^="/@"]',
            'ytd-reel-video-renderer[is-active] yt-reel-channel-bar-view-model #channel-name a',
            'ytd-reel-video-renderer[is-active] #channel-name a',
            '#metapanel #channel-name a',
            'ytd-reel-video-renderer[is-active] #channel-name'
        ]
    },

    // Interactions
    interactions: {
        subscribe: {
            button: "#metapanel yt-subscribe-button-view-model button",
            // Note: Subscription check is now done by examining button text/aria-label
            // instead of using a complex selector, as the previous check was unreliable
            check: "#metapanel > yt-reel-metapanel-view-model > div:nth-child(1) > yt-reel-channel-bar-view-model > div.ytReelChannelBarViewModelReelSubscribeButton > yt-subscribe-button-view-model > yt-animated-action > div > div > button > yt-touch-feedback-shape > div.yt-spec-touch-feedback-shape__fill"
        },
        like: {
            button: "#button-bar like-button-view-model button",
            // Check aria-pressed or specific class
            check: "#button-bar > reel-action-bar-view-model > like-button-view-model > toggle-button-view-model > button-view-model > label > button[aria-pressed='true']"
        },
        comment: {
            openButton: "#button-bar > reel-action-bar-view-model > button-view-model:nth-child(3) button",
            // Input logic is complex: placeholder -> input
            placeholder: "#placeholder-area",
            input: "#contenteditable-root[contenteditable='true']",
            submitButton: "#submit-button button, #submit-button yt-button-shape button"
        }
    },

    // Navigation / Container
    container: {
        shortsPlayer: '#shorts-player',
        activeSlide: 'ytd-reel-video-renderer[is-active]'
    }
};

// Export for module systems
if (typeof module !== 'undefined') {
    module.exports = SELECTORS;
}
