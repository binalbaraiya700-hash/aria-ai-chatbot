from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, date
import google.generativeai as genai
from dotenv import load_dotenv
import os
import razorpay
import json
from io import BytesIO
import PyPDF2
import base64
from PIL import Image
import requests

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'aria-aviation-secret-2025')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///aviation_db.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
CORS(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
chat_model = genai.GenerativeModel('gemini-2.0-flash-exp')
vision_model = genai.GenerativeModel('gemini-2.0-flash-exp')

# Razorpay
razorpay_client = razorpay.Client(auth=(
    os.getenv('RAZORPAY_KEY_ID'),
    os.getenv('RAZORPAY_KEY_SECRET')
))

ADMIN_EMAILS = ['binalbaraiya700@gmail.com']

# ==================== MODELS ====================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_premium = db.Column(db.Boolean, default=False)
    premium_price = db.Column(db.Integer, default=121)
    is_early_bird = db.Column(db.Boolean, default=False)
    signup_number = db.Column(db.Integer)
    daily_chat_seconds = db.Column(db.Integer, default=0)
    last_reset_date = db.Column(db.Date)
    total_chat_seconds = db.Column(db.Integer, default=0)
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    streak_days = db.Column(db.Integer, default=0)
    last_chat_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship('Message', backref='user', lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_user = db.Column(db.Boolean, nullable=False)
    category = db.Column(db.String(50), default='general')
    has_media = db.Column(db.Boolean, default=False)
    media_type = db.Column(db.String(20))
    media_url = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class AircraftDiagram(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100))
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    components = db.Column(db.Text)  # JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LearningModule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(100))  # aerodynamics, structures, etc
    content = db.Column(db.Text)
    video_url = db.Column(db.String(500))
    difficulty = db.Column(db.String(20))  # beginner, intermediate, advanced
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    amount = db.Column(db.Integer)
    razorpay_order_id = db.Column(db.String(100))
    razorpay_payment_id = db.Column(db.String(100))
    status = db.Column(db.String(20), default='created')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Screenshot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    image_data = db.Column(db.Text)  # base64
    analysis = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== HELPER FUNCTIONS ====================
def reset_daily_limit(user):
    today = date.today()
    if user.last_reset_date != today:
        user.daily_chat_seconds = 0
        user.last_reset_date = today
        db.session.commit()

def get_time_remaining(user):
    if user.is_premium:
        return 999999
    return max(0, 1200 - user.daily_chat_seconds)

def update_xp(user, amount=5):
    user.xp += amount
    new_level = (user.xp // 50) + 1
    leveled_up = new_level > user.level
    user.level = new_level
    db.session.commit()
    return leveled_up

def update_streak(user):
    today = date.today()
    if user.last_chat_date:
        diff = (today - user.last_chat_date).days
        if diff == 1:
            user.streak_days += 1
        elif diff > 1:
            user.streak_days = 1
    else:
        user.streak_days = 1
    user.last_chat_date = today
    db.session.commit()

# ==================== ROUTES ====================
@app.route('/')
@login_required
def home():
    reset_daily_limit(current_user)
    time_remaining = get_time_remaining(current_user)
    is_admin = current_user.email in ADMIN_EMAILS
    
    minutes = time_remaining // 60
    seconds = time_remaining % 60
    time_display = f"{minutes:02d}:{seconds:02d}"
    
    return render_template('dashboard.html',
                         user=current_user,
                         time_remaining=time_display,
                         is_admin=is_admin)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already registered'}), 400
        
        user_count = User.query.count()
        is_early_bird = user_count < 50
        
        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            signup_number=user_count + 1,
            is_early_bird=is_early_bird,
            premium_price=89 if is_early_bird else 121,
            last_reset_date=date.today()
        )
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({'success': True}), 201
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            return jsonify({'success': True})
        
        return jsonify({'error': 'Invalid credentials'}), 401
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    try:
        data = request.json
        user_message = data.get('message')
        category = data.get('category', 'general')
        
        reset_daily_limit(current_user)
        time_remaining = get_time_remaining(current_user)
        
        if time_remaining <= 0:
            return jsonify({
                'error': 'Daily limit reached!',
                'limit_reached': True
            }), 403
        
        # Generate AI response
        response = chat_model.generate_content(user_message)
        ai_response = response.text
        
        # Save messages
        user_msg = Message(user_id=current_user.id, message=user_message, is_user=True, category=category)
        ai_msg = Message(user_id=current_user.id, message=ai_response, is_user=False, category=category)
        
        db.session.add(user_msg)
        db.session.add(ai_msg)
        
        if not current_user.is_premium:
            current_user.daily_chat_seconds += 10
        
        leveled_up = update_xp(current_user, 5)
        update_streak(current_user)
        
        db.session.commit()
        
        return jsonify({
            'response': ai_response,
            'time_remaining': get_time_remaining(current_user),
            'level_up': leveled_up,
            'level': current_user.level,
            'xp': current_user.xp,
            'streak': current_user.streak_days
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analyze-screenshot', methods=['POST'])
@login_required
def analyze_screenshot():
    try:
        data = request.json
        image_data = data.get('image')  # base64
        
        # Remove data URL prefix
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        # Decode base64
        image_bytes = base64.b64decode(image_data)
        image = Image.open(BytesIO(image_bytes))
        
        # Save temporarily
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f'screenshot_{current_user.id}.png')
        image.save(temp_path)
        
        # Analyze with Gemini Vision
        with open(temp_path, 'rb') as img_file:
            vision_response = vision_model.generate_content([
                "Analyze this screenshot in detail. Describe what you see, identify any text, UI elements, or important information.",
                {"mime_type": "image/png", "data": img_file.read()}
            ])
        
        analysis = vision_response.text
        
        # Save to database
        screenshot = Screenshot(
            user_id=current_user.id,
            image_data=image_data[:5000],  # Store preview
            analysis=analysis
        )
        db.session.add(screenshot)
        db.session.commit()
        
        os.remove(temp_path)
        
        return jsonify({
            'success': True,
            'analysis': analysis
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/aircraft-diagrams')
@login_required
def aircraft_diagrams():
    diagrams = AircraftDiagram.query.all()
    return render_template('aircraft_diagrams.html', diagrams=diagrams)

@app.route('/learning-modules')
@login_required
def learning_modules():
    modules = LearningModule.query.all()
    return render_template('learning_modules.html', modules=modules)

@app.route('/profile')
@login_required
def profile():
    message_count = Message.query.filter_by(user_id=current_user.id, is_user=True).count()
    return render_template('profile.html',
                         user=current_user,
                         message_count=message_count)

@app.route('/history')
@login_required
def history():
    messages = Message.query.filter_by(user_id=current_user.id).order_by(
        Message.timestamp.desc()
    ).limit(100).all()
    return render_template('history.html', messages=messages)

@app.route('/admin')
@login_required
def admin():
    if current_user.email not in ADMIN_EMAILS:
        return redirect(url_for('home'))
    
    total_users = User.query.count()
    premium_users = User.query.filter_by(is_premium=True).count()
    total_messages = Message.query.count()
    total_revenue = db.session.query(db.func.sum(Payment.amount)).filter_by(status='success').scalar() or 0
    
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    
    return render_template('admin.html',
                         total_users=total_users,
                         premium_users=premium_users,
                         total_messages=total_messages,
                         total_revenue=total_revenue/100,
                         recent_users=recent_users)

@app.route('/create-order', methods=['POST'])
@login_required
def create_order():
    amount = current_user.premium_price * 100
    
    order = razorpay_client.order.create({
        'amount': amount,
        'currency': 'INR',
        'payment_capture': 1
    })
    
    payment = Payment(
        user_id=current_user.id,
        amount=current_user.premium_price,
        razorpay_order_id=order['id']
    )
    db.session.add(payment)
    db.session.commit()
    
    return jsonify({
        'order_id': order['id'],
        'amount': amount,
        'currency': 'INR',
        'key': os.getenv('RAZORPAY_KEY_ID')
    })

@app.route('/payment-success', methods=['POST'])
@login_required
def payment_success():
    data = request.json
    
    payment = Payment.query.filter_by(
        razorpay_order_id=data.get('razorpay_order_id')
    ).first()
    
    if payment:
        payment.razorpay_payment_id = data.get('razorpay_payment_id')
        payment.status = 'success'
        current_user.is_premium = True
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'error': 'Payment not found'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)