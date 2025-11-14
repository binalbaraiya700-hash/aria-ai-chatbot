// Screenshot Analysis Module for Aria AI
// Add this to your dashboard.html

class ScreenshotAnalyzer {
    constructor() {
        this.isAnalyzing = false;
        this.captureInterval = null;
        this.init();
    }

    init() {
        this.createUI();
        this.setupEventListeners();
    }

    createUI() {
        const floatingButton = document.createElement('div');
        floatingButton.id = 'screenshotButton';
        floatingButton.innerHTML = `
            <style>
                #screenshotButton {
                    position: fixed;
                    bottom: 100px;
                    right: 30px;
                    width: 60px;
                    height: 60px;
                    background: linear-gradient(135deg, #667eea, #764ba2);
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    cursor: pointer;
                    box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
                    z-index: 9999;
                    transition: all 0.3s ease;
                }

                #screenshotButton:hover {
                    transform: scale(1.1);
                    box-shadow: 0 8px 30px rgba(102, 126, 234, 0.6);
                }

                #screenshotButton.analyzing {
                    animation: pulse 1.5s infinite;
                    background: linear-gradient(135deg, #f093fb, #f5576c);
                }

                @keyframes pulse {
                    0%, 100% { transform: scale(1); }
                    50% { transform: scale(1.05); }
                }

                #screenshotButton svg {
                    width: 30px;
                    height: 30px;
                    fill: white;
                }

                .screenshot-modal {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.8);
                    display: none;
                    align-items: center;
                    justify-content: center;
                    z-index: 10000;
                }

                .screenshot-modal.active {
                    display: flex;
                }

                .screenshot-content {
                    background: white;
                    border-radius: 20px;
                    padding: 30px;
                    max-width: 600px;
                    width: 90%;
                    max-height: 80vh;
                    overflow-y: auto;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
                }

                .screenshot-content h2 {
                    color: #667eea;
                    margin-bottom: 20px;
                }

                .screenshot-preview {
                    width: 100%;
                    border-radius: 10px;
                    margin-bottom: 20px;
                    max-height: 300px;
                    object-fit: contain;
                }

                .analysis-result {
                    background: #f5f5f5;
                    padding: 15px;
                    border-radius: 10px;
                    margin-top: 15px;
                    color: #333;
                    line-height: 1.6;
                }

                .button-group {
                    display: flex;
                    gap: 10px;
                    margin-top: 20px;
                }

                .modal-button {
                    flex: 1;
                    padding: 12px;
                    border: none;
                    border-radius: 8px;
                    cursor: pointer;
                    font-weight: 600;
                    transition: all 0.3s;
                }

                .modal-button.primary {
                    background: linear-gradient(135deg, #667eea, #764ba2);
                    color: white;
                }

                .modal-button.secondary {
                    background: #e0e0e0;
                    color: #333;
                }

                .modal-button:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
                }

                .loading-spinner {
                    display: inline-block;
                    width: 20px;
                    height: 20px;
                    border: 3px solid rgba(255, 255, 255, 0.3);
                    border-radius: 50%;
                    border-top-color: white;
                    animation: spin 0.8s linear infinite;
                }

                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
            </style>

            <svg viewBox="0 0 24 24">
                <path d="M21 15v3c0 .55-.45 1-1 1H4c-.55 0-1-.45-1-1v-3c0-.55.45-1 1-1s1 .45 1 1v2h14v-2c0-.55.45-1 1-1s1 .45 1 1zM12 2C9.79 2 8 3.79 8 6s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4zm0 6c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2z"/>
                <circle cx="12" cy="12" r="2"/>
            </svg>
        `;
        document.body.appendChild(floatingButton);

        // Create Modal
        const modal = document.createElement('div');
        modal.id = 'screenshotModal';
        modal.className = 'screenshot-modal';
        modal.innerHTML = `
            <div class="screenshot-content">
                <h2>📸 Screenshot Analysis</h2>
                <div id="screenshotPreviewArea"></div>
                <div id="analysisResultArea"></div>
                <div class="button-group">
                    <button class="modal-button secondary" onclick="screenshotAnalyzer.closeModal()">Close</button>
                    <button class="modal-button primary" onclick="screenshotAnalyzer.retakeScreenshot()">Retake</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    setupEventListeners() {
        document.getElementById('screenshotButton').addEventListener('click', () => {
            this.captureScreen();
        });

        // Keyboard shortcut: Ctrl + Shift + S
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.shiftKey && e.key === 'S') {
                e.preventDefault();
                this.captureScreen();
            }
        });
    }

    async captureScreen() {
        try {
            // Check if browser supports screen capture
            if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
                alert('Screen capture is not supported in your browser. Please use Chrome, Edge, or Firefox.');
                return;
            }

            const stream = await navigator.mediaDevices.getDisplayMedia({
                video: { mediaSource: 'screen' }
            });

            const video = document.createElement('video');
            video.srcObject = stream;
            video.play();

            await new Promise(resolve => {
                video.onloadedmetadata = resolve;
            });

            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0);

            stream.getTracks().forEach(track => track.stop());

            const imageDataUrl = canvas.toDataURL('image/png');
            this.analyzeScreenshot(imageDataUrl);

        } catch (error) {
            console.error('Screenshot error:', error);
            if (error.name === 'NotAllowedError') {
                alert('Screen capture permission denied. Please allow screen sharing to use this feature.');
            } else {
                alert('Failed to capture screenshot: ' + error.message);
            }
        }
    }

    async analyzeScreenshot(imageDataUrl) {
        const modal = document.getElementById('screenshotModal');
        const previewArea = document.getElementById('screenshotPreviewArea');
        const resultArea = document.getElementById('analysisResultArea');

        modal.classList.add('active');
        document.getElementById('screenshotButton').classList.add('analyzing');

        previewArea.innerHTML = `<img src="${imageDataUrl}" class="screenshot-preview" alt="Captured screenshot">`;
        resultArea.innerHTML = `
            <div class="analysis-result">
                <div class="loading-spinner"></div>
                <span style="margin-left: 10px;">Analyzing screenshot with AI...</span>
            </div>
        `;

        try {
            // Send to backend for analysis
            const response = await fetch('/api/analyze-screenshot', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    image: imageDataUrl,
                    prompt: 'Analyze this screenshot and provide detailed information about what you see. If it\'s aviation-related, provide technical insights. If it\'s code, explain it. If it\'s a diagram, describe the components and their relationships.'
                })
            });

            if (!response.ok) {
                throw new Error('Analysis failed');
            }

            const data = await response.json();

            resultArea.innerHTML = `
                <div class="analysis-result">
                    <h3 style="margin-bottom: 10px; color: #667eea;">🤖 AI Analysis:</h3>
                    <p>${data.analysis || 'Analysis complete!'}</p>
                </div>
            `;

        } catch (error) {
            console.error('Analysis error:', error);
            resultArea.innerHTML = `
                <div class="analysis-result" style="background: #ffe0e0; color: #c62828;">
                    <strong>⚠️ Analysis Error:</strong><br>
                    ${error.message || 'Failed to analyze screenshot. Please try again.'}
                </div>
            `;
        } finally {
            document.getElementById('screenshotButton').classList.remove('analyzing');
        }
    }

    closeModal() {
        document.getElementById('screenshotModal').classList.remove('active');
    }

    retakeScreenshot() {
        this.closeModal();
        setTimeout(() => this.captureScreen(), 300);
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.screenshotAnalyzer = new ScreenshotAnalyzer();
    });
} else {
    window.screenshotAnalyzer = new ScreenshotAnalyzer();
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ScreenshotAnalyzer;
}