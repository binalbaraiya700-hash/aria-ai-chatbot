from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date
import google.generativeai as genai
from dotenv import load_dotenv
import os
import razorpay
import json
from io import BytesIO
import PyPDF2

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

db = SQLAlchemy(app)
CORS(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Gemini API Setup
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

# Razorpay Setup
razorpay_client = razorpay.Client(auth=(
    os.getenv('RAZORPAY_KEY_ID'),
    os.getenv('RAZORPAY_KEY_SECRET')
))

# ==================== MODELS ====================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_premium = db.Column(db.Boolean, default=False)
    premium_expiry = db.Column(db.DateTime, nullable=True)
    premium_price = db.Column(db.Integer, default=121)
    is_early_bird = db.Column(db.Boolean, default=False)
    signup_number = db.Column(db.Integer, nullable=True)
    daily_chat_seconds = db.Column(db.Integer, default=0)
    last_reset_date = db.Column(db.Date, nullable=True)
    total_chat_seconds = db.Column(db.Integer, default=0)
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    streak_days = db.Column(db.Integer, default=0)
    last_chat_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship('Message', backref='user', lazy=True, cascade='all, delete-orphan')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_user = db.Column(db.Boolean, nullable=False)
    category = db.Column(db.String(50), default='general')
    duration_seconds = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    razorpay_order_id = db.Column(db.String(100), nullable=False)
    razorpay_payment_id = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='created')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

class ScheduledMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    scheduled_time = db.Column(db.DateTime, nullable=False)
    is_sent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
        return 9999999
    return max(0, 1200 - user.daily_chat_seconds)

def format_time(seconds):
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"

def update_xp_and_level(user, xp_gain=5):
    user.xp += xp_gain
    new_level = (user.xp // 50) + 1
    if new_level > user.level:
        user.level = new_level
        return True
    return False

def update_streak(user):
    today = date.today()
    if user.last_chat_date:
        days_diff = (today - user.last_chat_date).days
        if days_diff == 1:
            user.streak_days += 1
        elif days_diff > 1:
            user.streak_days = 1
    else:
        user.streak_days = 1
    user.last_chat_date = today

def get_badges(user):
    badges = []
    if user.is_premium:
        badges.append({"name": "Premium", "icon": "⭐", "desc": "Premium Member"})
    if user.is_early_bird:
        badges.append({"name": "Early Bird", "icon": "🔥", "desc": "First 50 Users"})
    if user.level >= 5:
        badges.append({"name": "Expert", "icon": "🎓", "desc": "Reached Level 5"})
    if user.level >= 10:
        badges.append({"name": "Master", "icon": "👑", "desc": "Reached Level 10"})
    if user.streak_days >= 7:
        badges.append({"name": "Consistent", "icon": "🔥", "desc": "7 Day Streak"})
    if user.streak_days >= 30:
        badges.append({"name": "Dedicated", "icon": "💎", "desc": "30 Day Streak"})
    return badges

# ==================== ROUTES ====================
@app.route('/')
@login_required
def home():
    reset_daily_limit(current_user)
    time_remaining = get_time_remaining(current_user)
    is_admin = current_user.email == 'binalbaraiya700@gmail.com'
    badges = get_badges(current_user)
    return render_template('index.html', 
                         time_remaining=format_time(time_remaining),
                         user=current_user,
                         is_admin=is_admin,
                         badges=badges)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already registered'}), 400
        
        user_count = User.query.count()
        is_early_bird = user_count < 50
        premium_price = 89 if is_early_bird else 121
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)
        
        new_user = User(
            username=username,
            email=email,
            password=hashed_password,
            signup_number=user_count + 1,
            is_early_bird=is_early_bird,
            premium_price=premium_price,
            last_reset_date=date.today()
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Account created successfully!'}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        remember = data.get('remember', True)
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user, remember=remember, duration=timedelta(days=30))
            return jsonify({'success': True}), 200
        
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
    start_time = datetime.utcnow()
    
    reset_daily_limit(current_user)
    time_remaining = get_time_remaining(current_user)
    
    if time_remaining <= 0 and not current_user.is_premium:
        return jsonify({
            'response': '⏰ Daily 20-minute limit reached! Upgrade to Premium for unlimited chat time. ⭐',
            'limit_reached': True
        })
    
    data = request.get_json()
    user_message = data.get('message')
    category = data.get('category', 'general')
    
    try:
        user_msg = Message(
            user_id=current_user.id, 
            message=user_message, 
            is_user=True,
            category=category
        )
        db.session.add(user_msg)
        
        response = model.generate_content(user_message)
        ai_response = response.text
        
        end_time = datetime.utcnow()
        duration = int((end_time - start_time).total_seconds())
        
        if not current_user.is_premium:
            current_user.daily_chat_seconds += duration
        current_user.total_chat_seconds += duration
        
        level_up = update_xp_and_level(current_user, xp_gain=5)
        update_streak(current_user)
        
        ai_msg = Message(
            user_id=current_user.id,
            message=ai_response,
            is_user=False,
            category=category,
            duration_seconds=duration
        )
        db.session.add(ai_msg)
        db.session.commit()
        
        time_remaining = get_time_remaining(current_user)
        
        return jsonify({
            'response': ai_response,
            'time_remaining': time_remaining,
            'time_remaining_formatted': format_time(time_remaining),
            'duration': duration,
            'xp_gained': 5,
            'level': current_user.level,
            'total_xp': current_user.xp,
            'level_up': level_up,
            'streak': current_user.streak_days
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'response': f'Error: {str(e)}'}), 500

@app.route('/upload-document', methods=['POST'])
@login_required
def upload_document():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.pdf'):
        return jsonify({'error': 'Only PDF files allowed'}), 400
    
    try:
        pdf_reader = PyPDF2.PdfReader(BytesIO(file.read()))
        text_content = ""
        for page in pdf_reader.pages:
            text_content += page.extract_text()
        
        doc = Document(
            user_id=current_user.id,
            filename=file.filename,
            content=text_content[:10000]  # Limit to 10k chars
        )
        db.session.add(doc)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Document "{file.filename}" uploaded successfully!',
            'doc_id': doc.id
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/ask-document', methods=['POST'])
@login_required
def ask_document():
    data = request.get_json()
    doc_id = data.get('doc_id')
    question = data.get('question')
    
    doc = Document.query.get(doc_id)
    if not doc or doc.user_id != current_user.id:
        return jsonify({'error': 'Document not found'}), 404
    
    try:
        prompt = f"""Based on this document content:

{doc.content}

Answer this question: {question}

Provide a clear and concise answer based only on the document content."""
        
        response = model.generate_content(prompt)
        
        return jsonify({
            'response': response.text,
            'document': doc.filename
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/profile')
@login_required
def profile():
    badges = get_badges(current_user)
    docs = Document.query.filter_by(user_id=current_user.id).all()
    
    # Category-wise message count
    categories = db.session.query(
        Message.category,
        db.func.count(Message.id)
    ).filter_by(user_id=current_user.id, is_user=True).group_by(Message.category).all()
    
    category_stats = {cat: count for cat, count in categories}
    
    return render_template('profile.html',
                         user=current_user,
                         badges=badges,
                         documents=docs,
                         category_stats=category_stats)

@app.route('/history')
@login_required
def chat_history():
    messages = Message.query.filter_by(user_id=current_user.id).order_by(
        Message.timestamp.desc()
    ).all()
    
    from collections import defaultdict
    grouped_messages = defaultdict(list)
    for msg in messages:
        date_key = msg.timestamp.strftime('%d %b %Y')
        grouped_messages[date_key].append(msg)
    
    total_chats = len(messages)
    return render_template('history.html',
                         grouped_messages=dict(grouped_messages),
                         total_chats=total_chats)

@app.route('/api/delete-chat/<int:message_id>', methods=['POST'])
@login_required
def delete_chat(message_id):
    message = Message.query.get_or_404(message_id)
    if message.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    db.session.delete(message)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/clear-history', methods=['POST'])
@login_required
def clear_history():
    Message.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({'success': True, 'message': 'Chat history cleared!'})

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
    data = request.get_json()
    
    payment = Payment.query.filter_by(
        razorpay_order_id=data.get('razorpay_order_id')
    ).first()
    
    if payment:
        payment.razorpay_payment_id = data.get('razorpay_payment_id')
        payment.status = 'success'
        
        current_user.is_premium = True
        current_user.premium_expiry = datetime.utcnow() + timedelta(days=30)
        
        db.session.commit()
        
        return jsonify({'success': True})
    
    return jsonify({'error': 'Payment not found'}), 404

@app.route('/admin')
@login_required
def admin():
    if current_user.email != 'binalbaraiya700@gmail.com':
        return redirect(url_for('home'))
    
    total_users = User.query.count()
    premium_users = User.query.filter_by(is_premium=True).count()
    early_bird_users = User.query.filter_by(is_early_bird=True).count()
    total_revenue = db.session.query(db.func.sum(Payment.amount)).filter_by(status='success').scalar() or 0
    
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_payments = Payment.query.order_by(Payment.timestamp.desc()).limit(10).all()
    
    # Daily user registration stats (last 30 days)
    from sqlalchemy import func
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    daily_signups = db.session.query(
        func.date(User.created_at).label('date'),
        func.count(User.id).label('count')
    ).filter(User.created_at >= thirty_days_ago).group_by(func.date(User.created_at)).all()
    
    # Category usage stats
    category_usage = db.session.query(
        Message.category,
        func.count(Message.id)
    ).filter(Message.is_user == True).group_by(Message.category).all()
    
    return render_template('admin.html',
                         total_users=total_users,
                         premium_users=premium_users,
                         early_bird_users=early_bird_users,
                         total_revenue=total_revenue,
                         recent_users=recent_users,
                         recent_payments=recent_payments,
                         daily_signups=daily_signups,
                         category_usage=category_usage)

@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.email != 'binalbaraiya700@gmail.com':
        return redirect(url_for('home'))
    
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/make-premium/<int:user_id>', methods=['POST'])
@login_required
def make_premium(user_id):
    if current_user.email != 'binalbaraiya700@gmail.com':
        return jsonify({'error': 'Unauthorized'}), 403
    
    user = User.query.get(user_id)
    if user:
        user.is_premium = True
        user.premium_expiry = datetime.utcnow() + timedelta(days=30)
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'error': 'User not found'}), 404

# PWA Routes
@app.route('/static/manifest.json')
def manifest():
    return send_file('static/manifest.json', mimetype='application/json')

@app.route('/sw.js')
def service_worker():
    return send_file('static/sw.js', mimetype='application/javascript')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)