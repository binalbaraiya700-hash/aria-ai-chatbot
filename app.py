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

# ==================== ARIA BRAIN ====================
class ARIABrain:
    def __init__(self):
        self.personality = {
            'name': 'ARIA',
            'traits': ['friendly', 'caring', 'intelligent', 'helpful'],
            'language': 'hinglish'
        }
        
        self.conversation_memory = {}
    
    def get_system_prompt(self):
        return """You are ARIA - an advanced AI assistant like Claude.

YOUR PERSONALITY:
- Friendly, intelligent, and genuinely helpful
- Speak naturally in Hinglish (Hindi + English mix)
- Be conversational and warm
- No robotic responses

YOUR CAPABILITIES:
✅ Coding & Programming - Write, debug, explain code in any language
✅ Problem Solving - Math, logic, algorithms, technical questions
✅ Learning & Teaching - Explain concepts simply with examples
✅ News & Information - Discuss current events, trends, technology
✅ Creative Writing - Stories, content, ideas
✅ Career Advice - Resume tips, interview prep, skill guidance
✅ General Knowledge - Answer any topic with accurate information

RESPONSE STYLE:
- Give direct, helpful answers
- Use examples when explaining
- Be concise for simple questions
- Be detailed for complex topics
- Ask clarifying questions if needed
- Admit when you don't know something

CONVERSATION FLOW:
- Start responses naturally (no "As an AI...")
- Use conversational phrases: "Achha!", "Great question!", "Let me help!"
- Be encouraging and supportive
- Maintain context from previous messages

Remember: You're a helpful companion who can discuss anything - from coding bugs to career advice to news to creative projects. Be natural, be helpful, be ARIA! 😊"""
    
    def add_to_memory(self, session_id, user_msg, ai_msg):
        if session_id not in self.conversation_memory:
            self.conversation_memory[session_id] = []
        
        self.conversation_memory[session_id].append({
            'user': user_msg,
            'aria': ai_msg,
            'time': datetime.now().isoformat()
        })
        
        # Keep last 20 messages
        if len(self.conversation_memory[session_id]) > 20:
            self.conversation_memory[session_id] = self.conversation_memory[session_id][-20:]
    
    def get_context(self, session_id, last_n=5):
        if session_id not in self.conversation_memory:
            return ""
        
        recent = self.conversation_memory[session_id][-last_n:]
        context = "\n".join([
            f"User: {msg['user']}\nARIA: {msg['aria']}"
            for msg in recent
        ])
        return f"\n\nRecent conversation:\n{context}" if context else ""

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
        print("✅ Anthropic Claude initialized!")
    except:
        client = None
        print("⚠️ Anthropic initialization failed")
else:
    client = None
    print("⚠️ Anthropic not available")

# ==================== MODELS ====================
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
        print("✅ Database created")
        admin = User.query.filter_by(email='admin@aria.com').first()
        if not admin:
            admin = User(username='Admin', email='admin@aria.com', is_admin=True, is_premium=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin: admin@aria.com / admin123")
    except Exception as e:
        print(f"❌ Database error: {e}")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== ROUTES ====================
@app.route('/')
def index():
    # Generate session ID for guests
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
        
        # Get or create session ID
        session_id = session.get('session_id', str(uuid.uuid4()))
        session['session_id'] = session_id
        
        # Check if user is logged in
        is_guest = not current_user.is_authenticated
        user_id = current_user.id if current_user.is_authenticated else None
        # Get conversation context
        context = aria_brain.get_context(session_id)
        system_prompt = aria_brain.get_system_prompt()
        
        # Generate AI response
        if client:
            try:
                # Add context to message if available
                full_message = message
                if context:
                    full_message = f"{context}\n\nCurrent question: {message}"
                
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2000,
                    system=system_prompt,
                    messages=[{"role": "user", "content": full_message}]
                )
                ai_response = response.content[0].text
            except Exception as e:
                print(f"Anthropic error: {e}")
                ai_response = "Hey! 😊 I'm ARIA, your AI assistant. I'm currently having trouble connecting to my full capabilities, but I'm here to help! What would you like to know?"
        else:
            ai_response = "Hello! 😊 I'm ARIA - your AI assistant. I can help with coding, questions, learning, and much more. What can I help you with today?"
        
        # Save chat
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
            
            xp_needed = current_user.level * 100
            if current_user.xp >= xp_needed:
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
        return jsonify({'success': False, 'error': str(e)}), 500

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

@app.errorhandler(404)
def not_found(e):
    return redirect(url_for('index'))

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)