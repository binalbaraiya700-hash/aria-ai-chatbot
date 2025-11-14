// Voice Assistant Module for Aria AI
// Blackbox AI style voice calling feature

class VoiceAssistant {
    constructor() {
        this.isListening = false;
        this.isSpeaking = false;
        this.recognition = null;
        this.synthesis = window.speechSynthesis;
        this.conversation = [];
        this.init();
    }

    init() {
        this.setupSpeechRecognition();
        this.createUI();
        this.setupEventListeners();
    }

    setupSpeechRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        
        if (!SpeechRecognition) {
            console.error('Speech recognition not supported');
            return;
        }

        this.recognition = new SpeechRecognition();
        this.recognition.continuous = true;
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-US';

        this.recognition.onresult = (event) => {
            const transcript = Array.from(event.results)
                .map(result => result[0].transcript)
                .join('');
            
            this.updateTranscript(transcript);

            if (event.results[event.results.length - 1].isFinal) {
                this.processVoiceCommand(transcript);
            }
        };

        this.recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            this.stopListening();
        };

        this.recognition.onend = () => {
            if (this.isListening) {
                this.recognition.start();
            }
        };
    }

    createUI() {
        const container = document.createElement('div');
        container.id = 'voiceAssistantContainer';
        container.innerHTML = `
            <style>
                #voiceAssistantContainer {
                    position: fixed;
                    bottom: 30px;
                    right: 30px;
                    z-index: 9998;
                }

                .voice-button {
                    width: 70px;
                    height: 70px;
                    border-radius: 50%;
                    background: linear-gradient(135deg, #f093fb, #f5576c);
                    border: none;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    box-shadow: 0 5px 25px rgba(245, 87, 108, 0.5);
                    transition: all 0.3s ease;
                    position: relative;
                }

                .voice-button:hover {
                    transform: scale(1.1);
                    box-shadow: 0 8px 35px rgba(245, 87, 108, 0.7);
                }

                .voice-button.listening {
                    animation: voicePulse 1.5s infinite;
                }

                @keyframes voicePulse {
                    0%, 100% {
                        box-shadow: 0 5px 25px rgba(245, 87, 108, 0.5);
                        transform: scale(1);
                    }
                    50% {
                        box-shadow: 0 10px 40px rgba(245, 87, 108, 0.9);
                        transform: scale(1.05);
                    }
                }

                .voice-button svg {
                    width: 35px;
                    height: 35px;
                    fill: white;
                }

                .voice-panel {
                    position: absolute;
                    bottom: 90px;
                    right: 0;
                    width: 350px;
                    max-height: 500px;
                    background: white;
                    border-radius: 20px;
                    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
                    display: none;
                    flex-direction: column;
                    overflow: hidden;
                }

                .voice-panel.active {
                    display: flex;
                }

                .voice-header {
                    background: linear-gradient(135deg, #667eea, #764ba2);
                    color: white;
                    padding: 20px;
                    text-align: center;
                }

                .voice-header h3 {
                    margin: 0;
                    font-size: 20px;
                }

                .voice-header p {
                    margin: 5px 0 0;
                    font-size: 13px;
                    opacity: 0.9;
                }

                .voice-status {
                    padding: 15px;
                    background: #f5f5f5;
                    text-align: center;
                    font-size: 14px;
                    color: #666;
                }

                .voice-status.listening {
                    background: #e8f5e9;
                    color: #2e7d32;
                }

                .voice-status.speaking {
                    background: #e3f2fd;
                    color: #1976d2;
                }

                .transcript-area {
                    flex: 1;
                    padding: 15px;
                    overflow-y: auto;
                    min-height: 200px;
                    max-height: 300px;
                }

                .transcript-message {
                    margin-bottom: 15px;
                    padding: 10px;
                    border-radius: 10px;
                    font-size: 14px;
                    line-height: 1.5;
                }

                .transcript-message.user {
                    background: #e3f2fd;
                    color: #1565c0;
                    margin-left: 20px;
                }

                .transcript-message.ai {
                    background: #f3e5f5;
                    color: #6a1b9a;
                    margin-right: 20px;
                }

                .voice-controls {
                    padding: 15px;
                    border-top: 1px solid #e0e0e0;
                    display: flex;
                    gap: 10px;
                }

                .voice-control-btn {
                    flex: 1;
                    padding: 12px;
                    border: none;
                    border-radius: 10px;
                    cursor: pointer;
                    font-weight: 600;
                    transition: all 0.3s;
                }

                .voice-control-btn.start {
                    background: linear-gradient(135deg, #667eea, #764ba2);
                    color: white;
                }

                .voice-control-btn.stop {
                    background: linear-gradient(135deg, #f093fb, #f5576c);
                    color: white;
                }

                .voice-control-btn:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
                }

                .voice-control-btn:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }

                .waveform {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 3px;
                    height: 30px;
                    margin: 10px 0;
                }

                .waveform-bar {
                    width: 3px;
                    background: white;
                    border-radius: 3px;
                    animation: waveAnimation 1s ease-in-out infinite;
                }

                .waveform-bar:nth-child(1) { height: 10px; animation-delay: 0s; }
                .waveform-bar:nth-child(2) { height: 20px; animation-delay: 0.1s; }
                .waveform-bar:nth-child(3) { height: 25px; animation-delay: 0.2s; }
                .waveform-bar:nth-child(4) { height: 20px; animation-delay: 0.3s; }
                .waveform-bar:nth-child(5) { height: 10px; animation-delay: 0.4s; }

                @keyframes waveAnimation {
                    0%, 100% { height: 10px; }
                    50% { height: 30px; }
                }

                @media (max-width: 768px) {
                    .voice-panel {
                        width: calc(100vw - 40px);
                        right: -10px;
                    }
                }
            </style>

            <button class="voice-button" id="voiceMainButton">
                <svg viewBox="0 0 24 24">
                    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.91-3c-.49 0-.9.36-.98.85C16.52 14.2 14.47 16 12 16s-4.52-1.8-4.93-4.15c-.08-.49-.49-.85-.98-.85-.61 0-1.09.54-1 1.14.49 3 2.89 5.35 5.91 5.78V20c0 .55.45 1 1 1s1-.45 1-1v-2.08c3.02-.43 5.42-2.78 5.91-5.78.1-.6-.39-1.14-1-1.14z"/>
                </svg>
            </button>

            <div class="voice-panel" id="voicePanel">
                <div class="voice-header">
                    <h3>🎙️ AI Voice Assistant</h3>
                    <p>Speak naturally, I'm listening</p>
                    <div class="waveform" id="waveform" style="display: none;">
                        <div class="waveform-bar"></div>
                        <div class="waveform-bar"></div>
                        <div class="waveform-bar"></div>
                        <div class="waveform-bar"></div>
                        <div class="waveform-bar"></div>
                    </div>
                </div>

                <div class="voice-status" id="voiceStatus">
                    Click "Start" to begin conversation
                </div>

                <div class="transcript-area" id="transcriptArea">
                    <div style="text-align: center; color: #999; padding: 50px 20px;">
                        <p>No conversation yet</p>
                        <p style="font-size: 12px;">Start speaking to begin</p>
                    </div>
                </div>

                <div class="voice-controls">
                    <button class="voice-control-btn start" id="startVoiceBtn" onclick="voiceAssistant.startListening()">
                        Start
                    </button>
                    <button class="voice-control-btn stop" id="stopVoiceBtn" onclick="voiceAssistant.stopListening()" disabled>
                        Stop
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(container);
    }

    setupEventListeners() {
        document.getElementById('voiceMainButton').addEventListener('click', () => {
            const panel = document.getElementById('voicePanel');
            panel.classList.toggle('active');
        });

        // Close panel when clicking outside
        document.addEventListener('click', (e) => {
            const container = document.getElementById('voiceAssistantContainer');
            const panel = document.getElementById('voicePanel');
            if (!container.contains(e.target) && panel.classList.contains('active')) {
                panel.classList.remove('active');
            }
        });
    }

    startListening() {
        if (!this.recognition) {
            alert('Voice recognition is not supported in your browser. Please use Chrome or Edge.');
            return;
        }

        this.isListening = true;
        this.recognition.start();

        document.getElementById('voiceMainButton').classList.add('listening');
        document.getElementById('waveform').style.display = 'flex';
        document.getElementById('voiceStatus').className = 'voice-status listening';
        document.getElementById('voiceStatus').textContent = '🎤 Listening... Speak now';
        document.getElementById('startVoiceBtn').disabled = true;
        document.getElementById('stopVoiceBtn').disabled = false;
    }

    stopListening() {
        this.isListening = false;
        if (this.recognition) {
            this.recognition.stop();
        }

        document.getElementById('voiceMainButton').classList.remove('listening');
        document.getElementById('waveform').style.display = 'none';
        document.getElementById('voiceStatus').className = 'voice-status';
        document.getElementById('voiceStatus').textContent = 'Voice assistant stopped';
        document.getElementById('startVoiceBtn').disabled = false;
        document.getElementById('stopVoiceBtn').disabled = true;
    }

    updateTranscript(text) {
        const status = document.getElementById('voiceStatus');
        status.textContent = `🎤 "${text}"`;
    }

    async processVoiceCommand(transcript) {
        const trimmed = transcript.trim();
        if (!trimmed) return;

        this.addMessage('user', trimmed);

        document.getElementById('voiceStatus').className = 'voice-status speaking';
        document.getElementById('voiceStatus').textContent = '💭 AI is thinking...';

        try {
            const response = await fetch('/api/voice-chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ message: trimmed })
            });

            const data = await response.json();
            const aiResponse = data.response || 'I understand. How can I help you further?';

            this.addMessage('ai', aiResponse);
            this.speak(aiResponse);

        } catch (error) {
            console.error('Voice chat error:', error);
            const errorMsg = 'Sorry, I encountered an error. Please try again.';
            this.addMessage('ai', errorMsg);
            this.speak(errorMsg);
        }
    }

    addMessage(type, text) {
        const area = document.getElementById('transcriptArea');
        
        // Clear placeholder
        if (area.querySelector('div[style*="text-align: center"]')) {
            area.innerHTML = '';
        }

        const message = document.createElement('div');
        message.className = `transcript-message ${type}`;
        message.textContent = text;
        area.appendChild(message);
        area.scrollTop = area.scrollHeight;

        this.conversation.push({ role: type, content: text });
    }

    speak(text) {
        if (this.synthesis.speaking) {
            this.synthesis.cancel();
        }

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;

        utterance.onstart = () => {
            this.isSpeaking = true;
            document.getElementById('voiceStatus').className = 'voice-status speaking';
            document.getElementById('voiceStatus').textContent = '🔊 AI is speaking...';
        };

        utterance.onend = () => {
            this.isSpeaking = false;
            if (this.isListening) {
                document.getElementById('voiceStatus').className = 'voice-status listening';
                document.getElementById('voiceStatus').textContent = '🎤 Listening...';
            }
        };

        this.synthesis.speak(utterance);
    }
}

// Initialize
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.voiceAssistant = new VoiceAssistant();
    });
} else {
    window.voiceAssistant = new VoiceAssistant();
}

// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = VoiceAssistant;
}