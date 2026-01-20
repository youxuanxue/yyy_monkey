/**
 * UI Overlay to show status on Shorts page
 */
const UIOverlay = {
    element: null,

    init() {
        if (this.element) return;

        this.element = document.createElement('div');
        this.element.id = 'ysh-overlay';
        Object.assign(this.element.style, {
            position: 'fixed',
            top: '80px',
            right: '20px',
            zIndex: '9999',
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            color: 'white',
            padding: '10px 15px',
            borderRadius: '8px',
            fontFamily: 'sans-serif',
            fontSize: '14px',
            pointerEvents: 'none', // Click through
            transition: 'opacity 0.3s',
            display: 'flex',
            flexDirection: 'column',
            gap: '5px'
        });

        document.body.appendChild(this.element);
        this.hide();
    },

    show(status, details = '', type = 'info') {
        if (!this.element) this.init();

        let icon = '🤖';
        let color = 'white';

        switch (type) {
            case 'success':
                icon = '✅';
                color = '#4caf50';
                break;
            case 'skip':
                icon = '⏭️';
                color = '#9e9e9e';
                break;
            case 'processing':
                icon = '🧠';
                color = '#2196f3';
                break;
            case 'error':
                icon = '❌';
                color = '#f44336';
                break;
        }

        this.element.innerHTML = `
            <div style="font-weight:bold; display:flex; align-items:center; gap:5px;">
                <span>${icon}</span>
                <span>${status}</span>
            </div>
            ${details ? `<div style="font-size:12px; color:#ddd;">${details}</div>` : ''}
        `;
        
        this.element.style.borderLeft = `4px solid ${color}`;
        this.element.style.opacity = '1';
        
        // Auto hide after some time if it's a result
        if (type !== 'processing') {
            setTimeout(() => {
                this.fadeOut();
            }, 4000);
        }
    },

    fadeOut() {
        if (this.element) {
            this.element.style.opacity = '0';
        }
    },

    hide() {
        if (this.element) {
            this.element.style.opacity = '0';
        }
    }
};
