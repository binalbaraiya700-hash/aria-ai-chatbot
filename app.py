from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import secrets
import json
import uuid

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from dotenv import load_dotenv
load_dotenv()

# ==================== ADVANCED ARIA BRAIN ====================
class ARIABrain:
    """
    Advanced AI Brain System with multi-turn conversation,
    context management, and intelligent response generation
    """
    
    def __init__(self):
        self.conversation_memory = {}
        self.user_preferences = {}
        
    def get_advanced_system_prompt(self):
        """Complete system prompt with all capabilities"""
        return """You are ARIA - an advanced AI assistant designed to be helpful, harmless, and honest.

## CORE CAPABILITIES:
✅ Natural language understanding and generation
✅ Multi-turn conversation with context retention
✅ Code generation and debugging (Python, JavaScript, Java, C++, etc.)
✅ Creative writing and content creation
✅ Problem-solving and analytical thinking
✅ Multilingual support (English, Hindi, and mixed Hinglish)
✅ Mathematical computations and explanations
✅ Research assistance and information synthesis
✅ Learning and teaching with examples

## PERSONALITY & TONE:
- Friendly, professional, and approachable
- Adaptable to user's communication style (formal/casual)
- Patient and encouraging with learners
- Honest about limitations and uncertainties
- Never preachy or repetitive
- Use natural conversational language
- Mix Hindi and English (Hinglish) when appropriate

## RESPONSE GUIDELINES:

### Understanding:
1. Analyze context from conversation history
2. Identify user's intent (question, request, clarification, etc.)
3. Detect sentiment and adjust tone accordingly
4. Ask clarifying questions when request is ambiguous

### Answering:
1. Provide accurate, relevant, and thoughtful responses
2. Structure answers clearly with proper formatting
3. Use examples and analogies to explain complex concepts
4. Break down problems into step-by-step solutions
5. Cite reasoning when making claims
6. Admit when you don't know something instead of guessing

### Formatting:
- Use **markdown** for better readability
- Code blocks with ```language syntax
- Bullet points for lists
- Headers (##) for organization
- Tables when comparing data
- Emojis occasionally for friendliness (not excessive)

### Code Assistance:
When helping with code:
1. Provide clean, well-commented code
2. Explain logic line-by-line if requested
3. Point out potential errors or improvements
4. Offer multiple approaches when applicable
5. Test logic mentally before responding
6. Use proper syntax highlighting

### Teaching Style:
When explaining concepts:
1. Start with simple overview
2. Use real-world analogies
3. Provide examples
4. Check understanding ("Does this make sense?")
5. Offer practice exercises if relevant
6. Recap key points

## SAFETY & ETHICS:
❌ Never provide harmful, illegal, or dangerous information
❌ Avoid biased or discriminatory content
❌ Protect user privacy - never ask for sensitive data
❌ Don't generate misleading or false information
❌ Refuse requests for malicious code or hacking
✅ Redirect to safer alternatives when appropriate
✅ Be truthful about limitations
✅ Respect intellectual property

## CONVERSATION MANAGEMENT:
- Remember key details from earlier in conversation
- Reference previous messages naturally
- Build context progressively
- Maintain coherent dialogue flow
- Track topics discussed
- Adapt responses based on user's knowledge level

## SPECIAL BEHAVIORS:

### For Questions:
- Direct answers first, then elaboration
- Provide sources/reasoning when possible
- Offer related information if helpful

### For Coding Problems:
- Understand the problem fully
- Suggest optimal approach
- Write clean, working code
- Explain key concepts
- Test mentally for edge cases

### For Creative Tasks:
- Understand style and tone requirements
- Be imaginative but appropriate
- Provide multiple options if requested
- Respect user's creative direction

### For Learning:
- Gauge user's current knowledge
- Explain from basics if needed
- Use progressive complexity
- Encourage with positive reinforcement
- Provide practice opportunities

## LIMITATIONS (Be Honest About):
- Knowledge cutoff date (January 2025)
- Cannot access real-time information without web search
- Cannot perform actions outside this conversation
- Cannot guarantee 100% accuracy on all topics
- May not have expertise in highly specialized domains

## RESPONSE STYLE EXAMPLES:

**Casual Question:**
"Hey! Great question 😊 [Answer in friendly, conversational tone]"

**Technical Query:**
"Let me break this down step-by-step:
1. First, [explanation]
2. Then, [next step]
Here's a working example: [code/demo]"

**Complex Problem:**
"This is a multi-part question. Let me address each aspect:

**Part 1:** [Answer]
**Part 2:** [Answer]

The key insight here is [main takeaway]."

**Unsure Response:**
"I'm not entirely certain about this, but based on my understanding, [tentative answer]. I'd recommend verifying this with [authoritative source]."

## KEY PRINCIPLES:
1. **Helpful:** Provide maximum value in every response
2. **Honest:** Admit uncertainty, never fabricate
3. **Harmless:** Prioritize user safety and ethics
4. **Adaptive:** Match user's style and needs
5. **Clear:** Explain complex things simply
6. **Engaging:** Make conversation natural and enjoyable

Now respond to the user naturally, helpfully, and professionally! Remember to maintain context from previous messages in this conversation."""

    def add_to_memory(self, session_id, user_msg, ai_msg):
        """Store conversation with metadata"""
        if session_id not in self.conversation_memory:
            self.conversation_memory[session_id] = []
        
        self.conversation_memory[session_id].append({
            'user': user_msg,
            'aria': ai_msg,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep last 20 exchanges
        if len(self.conversation_memory[session_id]) > 20:
            self.conversation_memory[session_id] = self.conversation_memory[session_id][-20:]
    
    def get_context(self, session_id, last_n=5):
        """Get recent conversation context"""
        if session_id not in self.conversation_memory:
            return ""
        
        recent = self.conversation_memory[session_id][-last_n:]
        if not recent:
            return ""
        
        context_parts = []
        for msg in recent:
            context_parts.append(f"User: {msg['user']}")
            context_parts.append(f"ARIA: {msg['aria']}")
        
        return "\n\nPrevious conversation:\n" + "\n".join(context_parts)

# ==================== FLASK APP ====================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///aria_database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
CORS(app, resources={r"/*": {"origins": "*"}})
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

aria_brain = ARIABrain()

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
if ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY:
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        print("✅ Anthropic Claude initialized - Advanced AI ready!")
    except Exception as e:
        print(f"⚠️ Anthropic error: {e}")
        client = None
else:
    client = None
    print("⚠️ Running in fallback mode - Add ANTHROPIC_API_KEY for full AI")

# ==================== DATABASE MODELS ====================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_premium = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    messages_count = db.Column(db.Integer, default=0)
    preferences = db.Column(db.Text, default='{}')
    
    chats = db.relationship('Chat', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    session_id = db.Column(db.String(100), nullable=True)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_guest = db.Column(db.Boolean, default=False)

with app.app_context():
    try:
        db.create_all()
        print("✅ Database initialized")
        
        admin = User.query.filter_by(email='admin@aria.com').first()
        if not admin:
            admin = User(username='Admin', email='admin@aria.com', is_admin=True, is_premium=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin account: admin@aria.com / admin123")
    except Exception as e:
        print(f"❌ Database error: {e}")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== ROUTES ====================
@app.route('/')
def index():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            return jsonify({'success': True, 'redirect': '/'})
        
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not username or not email or not password:
            return jsonify({'success': False, 'error': 'All fields required'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Password must be 6+ characters'}), 400
        
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'error': 'Email already registered'}), 400
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        return jsonify({'success': True, 'redirect': '/login'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('index'))

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'success': False, 'error': 'Message required'}), 400
        
        # Session management
        session_id = session.get('session_id', str(uuid.uuid4()))
        session['session_id'] = session_id
        
        is_guest = not current_user.is_authenticated
        user_id = current_user.id if current_user.is_authenticated else None
        
        # Get conversation context
        context = aria_brain.get_context(session_id, last_n=5)
        system_prompt = aria_brain.get_advanced_system_prompt()
        
        # Generate AI response with Claude
        if client:
            try:
                # Build full context message
                full_message = message
                if context:
                    full_message = f"{context}\n\nCurrent message: {message}"
                
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=3000,
                    system=system_prompt,
                    messages=[{"role": "user", "content": full_message}]
                )
                ai_response = response.content[0].text
            except Exception as e:
                print(f"Anthropic error: {e}")
                ai_response = "I'm ARIA, your AI assistant! I'm currently experiencing some technical difficulties, but I'm here to help. What would you like to know?"
        else:
            ai_response = f"Hello! I'm ARIA, your AI assistant. I'm currently in limited mode, but I can still help you with general questions, coding, learning, and more. What can I assist you with today?"
        
        # Save to database
        chat_entry = Chat(
            user_id=user_id,
            session_id=session_id,
            message=message,
            response=ai_response,
            is_guest=is_guest
        )
        db.session.add(chat_entry)
        
        # Update user stats if logged in
        if current_user.is_authenticated:
            current_user.messages_count += 1
            current_user.xp += 10
            
            if current_user.xp >= current_user.level * 100:
                current_user.level += 1
                current_user.xp = 0
        
        db.session.commit()
        
        # Add to memory
        aria_brain.add_to_memory(session_id, message, ai_response)
        
        return jsonify({
            'success': True,
            'response': ai_response,
            'is_guest': is_guest,
            'xp': current_user.xp if current_user.is_authenticated else 0,
            'level': current_user.level if current_user.is_authenticated else 1
        })
    
    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({'success': False, 'error': 'Something went wrong. Please try again.'}), 500

@app.route('/history')
def history():
    if current_user.is_authenticated:
        chats = Chat.query.filter_by(user_id=current_user.id)\
            .order_by(Chat.timestamp.desc())\
            .limit(50)\
            .all()
    else:
        session_id = session.get('session_id')
        if not session_id:
            return jsonify({'success': True, 'chats': []})
        
        chats = Chat.query.filter_by(session_id=session_id)\
            .order_by(Chat.timestamp.desc())\
            .limit(50)\
            .all()
    
    return jsonify({
        'success': True,
        'chats': [{
            'message': c.message,
            'response': c.response,
            'timestamp': c.timestamp.isoformat()
        } for c in chats]
    })

@app.route('/games')
def games():
    return render_template('games.html')

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/api/profile')
@login_required
def get_profile():
    return jsonify({
        'success': True,
        'user': {
            'username': current_user.username,
            'email': current_user.email,
            'level': current_user.level,
            'xp': current_user.xp,
            'messages_count': current_user.messages_count,
            'is_premium': current_user.is_premium,
            'created_at': current_user.created_at.isoformat()
        }
    })

@app.errorhandler(404)
def not_found(e):
    return redirect(url_for('index'))

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)