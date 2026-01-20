/**
 * LLM Client for communicating with Ollama/OpenAI
 */
class LLMClient {
    constructor(config = {}) {
        this.config = {
            apiBaseUrl: 'http://localhost:11434/v1',
            apiKey: 'ollama',
            model: 'qwen2.5:3b',
            ...config
        };
    }

    updateConfig(newConfig) {
        this.config = { ...this.config, ...newConfig };
    }

    /**
     * Call LLM to analyze video
     * @param {object} videoInfo 
     * @param {string} systemPrompt 
     * @returns {Promise<object>}
     */
    async analyzeVideo(videoInfo, systemPrompt) {
        const userPrompt = this._formatUserPrompt(videoInfo);
        // Ensure standard endpoint structure
        const baseUrl = this.config.apiBaseUrl.replace(/\/$/, '');
        
        try {
            const response = await fetch(`${baseUrl}/chat/completions`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.config.apiKey}`
                },
                body: JSON.stringify({
                    model: this.config.model,
                    messages: [
                        { role: 'system', content: systemPrompt },
                        { role: 'user', content: userPrompt }
                    ],
                    temperature: 0.7,
                    max_tokens: 300,
                    response_format: { type: 'json_object' }
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API Error: ${response.status} - ${errorText}`);
            }

            const data = await response.json();
            return this._parseResponse(data);
        } catch (error) {
            console.error('LLM Call Failed:', error);
            return this._getErrorResponse(error.message);
        }
    }

    _formatUserPrompt(info) {
        return `【视频标题】\n${info.title || '无'}`;
    }

    _parseResponse(data) {
        try {
            const content = data.choices[0].message.content;
            // Handle potential markdown code blocks
            const jsonStr = content.replace(/```json\n|\n```/g, '').trim();
            const result = JSON.parse(jsonStr);
            return {
                success: true,
                result: result
            };
        } catch (e) {
            console.error('Parse Error:', e);
            return {
                success: false,
                error: 'Failed to parse JSON response',
                raw: data
            };
        }
    }

    _getErrorResponse(msg) {
        return {
            success: false,
            error: msg
        };
    }
}
