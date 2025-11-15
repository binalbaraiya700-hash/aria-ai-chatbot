from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import json
import secrets
import google.generativeai as genai
from dotenv import load_dotenv
import PyPDF2
import io

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize extensions
db = SQLAlchemy(app)
CORS(app, resources={r"/*": {"origins": "*"}})
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configure Gemini AI
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    print("Warning: GEMINI_API_KEY not found!")

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_premium = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    experience = db.Column(db.String(50), default='beginner')
    interest = db.Column(db.String(50), default='general')
    
    # Gamification
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    streak = db.Column(db.Integer, default=0)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    badges = db.Column(db.Text, default='[]')  # JSON array
    
    # Usage tracking
    messages_count = db.Column(db.Integer, default=0)
    messages_today = db.Column(db.Integer, default=0)
    last_message_date = db.Column(db.Date, default=datetime.utcnow().date)
    
    chats = db.relationship('Chat', backref='user', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.Column(db.String(50), default='general')

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='INR')
    status = db.Column(db.String(20), default='pending')
    razorpay_order_id = db.Column(db.String(100))
    razorpay_payment_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create database tables
with app.app_context():
    try:
        db.create_all()
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"❌ Database error: {e}")

# Routes
@app.route('/')
@login_required
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        print(f"❌ Index error: {e}")
        return jsonify({'error': 'Dashboard template not found'}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    user = User.query.filter_by(email=email).first()
    
    if user and user.check_password(password):
        login_user(user)
        return jsonify({
            'success': True,
            'redirect': '/admin' if user.is_admin else '/'
        })
    
    return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    experience = data.get('experience', 'beginner')
    interest = data.get('interest', 'general')
    
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'error': 'Email already registered'}), 400
    
    user = User(
        username=username,
        email=email,
        experience=experience,
        interest=interest
    )
    user.set_password(password)
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({'success': True, 'redirect': '/login'})

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    data = request.get_json()
    message = data.get('message', '')
    category = data.get('category', 'general')
    
    # Update message count
    today = datetime.utcnow().date()
    if current_user.last_message_date != today:
        current_user.messages_today = 0
        current_user.last_message_date = today
    
    # Check limits for free users
    if not current_user.is_premium:
        if current_user.messages_today >= 50:
            return jsonify({
                'success': False,
                'error': 'Daily message limit reached. Upgrade to premium for unlimited messages.'
            }), 429
    
    try:
        # Generate AI response
        if GEMINI_API_KEY:
            context = f"User experience level: {current_user.experience}. Interest: {current_user.interest}. Category: {category}."
            full_prompt = f"{context}\n\nUser question: {message}"
            
            response = model.generate_content(full_prompt)
            ai_response = response.text
        else:
            ai_response = "AI service temporarily unavailable. Please check API configuration."
        
        # Save chat
        chat = Chat(
            user_id=current_user.id,
            message=message,
            response=ai_response,
            category=category
        )
        db.session.add(chat)
        
        # Update user stats
        current_user.messages_count += 1
        current_user.messages_today += 1
        current_user.xp += 10
        current_user.last_active = datetime.utcnow()

        # Level up logic
        xp_needed = current_user.level * 100
        while current_user.xp >= xp_needed:
            current_user.xp -= xp_needed
            current_user.level += 1
            xp_needed = current_user.level * 100
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'response': ai_response,
            'xp': current_user.xp,
            'level': current_user.level,
            'messages_left': 50 - current_user.messages_today if not current_user.is_premium else -1
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analyze-screenshot', methods=['POST'])
@login_required
def analyze_screenshot():
    try:
        data = request.get_json()
        image_data = data.get('image', '')
        prompt = data.get('prompt', 'Analyze this image')
        
        if not GEMINI_API_KEY:
            return jsonify({'analysis': 'Screenshot analysis unavailable - API not configured'}), 503
        
        # In production, you would process the base64 image with Gemini Vision
        # For now, return a placeholder
        analysis = "Screenshot analysis feature is available. The image shows: [AI analysis would appear here]"
        
        return jsonify({'analysis': analysis})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/voice-chat', methods=['POST'])
@login_required
def voice_chat():
    try:
        data = request.get_json()
        message = data.get('message', '')
        
        if not GEMINI_API_KEY:
            return jsonify({'response': 'Voice assistant unavailable - API not configured'}), 503
        
        response = model.generate_content(f"Respond conversationally to: {message}")
        
        return jsonify({'response': response.text})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/learning')
@login_required
def learning():
    return render_template('learning.html')

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    return render_template('admin.html')

@app.route('/history')
@login_required
def history():
    chats = Chat.query.filter_by(user_id=current_user.id).order_by(Chat.timestamp.desc()).limit(50).all()
    return jsonify({
        'chats': [{
            'message': chat.message,
            'response': chat.response,
            'timestamp': chat.timestamp.isoformat(),
            'category': chat.category
        } for chat in chats]
    })

@app.errorhandler(404)
def not_found(e):
    return render_template('login.html'), 404

@app.errorhandler(500)
def internal_error(e):
    print(f"❌ 500 Error: {e}")
    return jsonify({
        'error': 'Internal server error',
        'details': str(e),
        'suggestion': 'Check logs for details'
    }), 500

# Production server configuration
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)