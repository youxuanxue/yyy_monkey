/**
 * Interaction Handler
 * Depends on SELECTORS from utils/selectors.js
 */

const Interactor = {
    async perform(actions, commentText) {
        console.log('[Interactor] Performing actions:', actions);

        if (actions.subscribe) {
            await this.subscribe();
            // Random wait between actions to make behavior more natural
            const delay = Math.floor(Math.random() * 3000); // 0-3000ms
            console.log(`[Interactor] Waiting ${delay}ms before next action...`);
            await this._sleep(delay);
        }

        if (actions.like) {
            await this.like();
            // Random wait between actions to make behavior more natural
            const delay = Math.floor(Math.random() * 3000); // 0-3000ms
            console.log(`[Interactor] Waiting ${delay}ms before next action...`);
            await this._sleep(delay);
        }

        if (actions.comment && commentText) {
            await this.comment(commentText);
            // Comment already has internal delays, but add a random delay after completion
            const delay = Math.floor(Math.random() * 3000); // 0-3000ms
            console.log(`[Interactor] Waiting ${delay}ms before next action...`);
            await this._sleep(delay);
        }

        if (actions.swipe) {
            await this.swipeNext();
        }
    },

    async swipeNext() {
        console.log('[Interactor] Swiping to next video...');
        // Dispatch ArrowDown event
        const event = new KeyboardEvent('keydown', {
            key: 'ArrowDown',
            code: 'ArrowDown',
            keyCode: 40,
            bubbles: true,
            cancelable: true
        });
        document.body.dispatchEvent(event);
    },

    async subscribe() {
        const sel = SELECTORS.interactions.subscribe;
        
        // Find the subscribe button first
        const btn = document.querySelector(sel.button);
        if (!btn) {
            console.warn('[Interactor] Subscribe button not found');
            return;
        }

        // Check if already subscribed by examining multiple indicators
        const buttonText = btn.textContent?.trim() || '';
        const ariaLabel = btn.getAttribute('aria-label') || '';
        const buttonTextLower = buttonText.toLowerCase();
        const ariaLabelLower = ariaLabel.toLowerCase();
        
        // Check button text (YouTube shows "Subscribed" when subscribed)
        const hasSubscribedText = buttonTextLower.includes('subscribed') || 
                                  buttonTextLower.includes('已订阅');
        
        // Check aria-label
        const hasSubscribedAria = ariaLabelLower.includes('subscribed') || 
                                  ariaLabelLower.includes('已订阅') ||
                                  ariaLabelLower.includes('unsubscribe') ||
                                  ariaLabelLower.includes('取消订阅');
        
        // Check parent element attributes
        const subscribeButtonModel = btn.closest('yt-subscribe-button-view-model');
        const hasSubscribedAttr = subscribeButtonModel?.hasAttribute('subscribed') ||
                                  subscribeButtonModel?.getAttribute('subscribed') === 'true' ||
                                  subscribeButtonModel?.getAttribute('subscribed') === '';
        
        // Check for subscribed state class or style
        const hasSubscribedClass = btn.classList.contains('subscribed') ||
                                   btn.closest('.subscribed') !== null;
        
        const isSubscribed = hasSubscribedText || hasSubscribedAria || hasSubscribedAttr || hasSubscribedClass;

        // Debug logging
        console.log('[Interactor] Subscribe check:', {
            buttonText,
            ariaLabel,
            hasSubscribedText,
            hasSubscribedAria,
            hasSubscribedAttr,
            hasSubscribedClass,
            isSubscribed
        });

        if (isSubscribed) {
            console.log('[Interactor] Already subscribed.');
            return;
        }

        // Not subscribed, click the button
        console.log('[Interactor] Clicking subscribe...');
        btn.click();
        await this._sleep(1000);
    },

    async like() {
        const sel = SELECTORS.interactions.like;
        if (this._exists(sel.check)) {
            console.log('[Interactor] Already liked.');
            return;
        }

        const btn = document.querySelector(sel.button);
        if (btn) {
            console.log('[Interactor] Clicking like...');
            btn.click();
            await this._sleep(1000);
        } else {
            console.warn('[Interactor] Like button not found');
        }
    },

    async comment(text) {
        const sel = SELECTORS.interactions.comment;
        
        // 1. Open Comment Section
        const openBtn = document.querySelector(sel.openButton);
        if (!openBtn) {
            console.warn('[Interactor] Comment button not found');
            return;
        }
        openBtn.click();
        await this._sleep(2000); // Wait longer for modal

        // 2. Find Input - Retry Logic
        let input = null;
        for (let i = 0; i < 3; i++) {
             // Try direct input
             input = document.querySelector(sel.input);
             
             // Try placeholder if input not found (click to activate)
             if (!input && sel.placeholder) {
                 const placeholder = document.querySelector(sel.placeholder);
                 if (placeholder) {
                     console.log('[Interactor] Clicking placeholder...');
                     placeholder.click();
                     await this._sleep(500);
                 }
             }
             
             if (input) break;
             await this._sleep(1000);
        }

        if (!input) {
            console.warn('[Interactor] Comment input not found after retries');
            // Try to close to reset state
            this._closeComments();
            return;
        }

        // 3. Input Text
        console.log('[Interactor] Writing comment:', text);
        input.focus();
        document.execCommand('insertText', false, text);
        
        // Dispatch events just in case
        input.dispatchEvent(new Event('input', { bubbles: true }));
        await this._sleep(1000);

        // 4. Submit
        const submitBtn = document.querySelector(sel.submitButton);
        if (submitBtn) {
            submitBtn.click();
            console.log('[Interactor] Comment submitted');
            await this._sleep(2000);
            this._closeComments();
        } else {
            console.warn('[Interactor] Submit button not found');
        }
    },

    _closeComments() {
        // 5. Close Comment Section
        const closeBtn = document.querySelector("#visibility-button button, #close-button button");
        if (closeBtn) closeBtn.click();
    },

    _exists(selector) {
        return !!document.querySelector(selector);
    },

    _sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
};
