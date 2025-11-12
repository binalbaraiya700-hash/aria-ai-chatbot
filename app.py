from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta, date
import razorpay

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Config
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Admin emails
ADMIN_EMAILS = ['binalbaraiya700@gmail.com']

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Razorpay setup
razorpay_client = razorpay.Client(auth=(
    os.getenv('RAZORPAY_KEY_ID', ''),
    os.getenv('RAZORPAY_KEY_SECRET', '')
))

# Gemini AI setup
api_key = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.0-flash')

# ==================== DATABASE MODELS ====================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    
    # Premium features
    is_premium = db.Column(db.Boolean, default=False)
    premium_expiry = db.Column(db.DateTime, nullable=True)
    premium_price = db.Column(db.Integer, default=121)
    is_early_bird = db.Column(db.Boolean, default=False)
    signup_number = db.Column(db.Integer, nullable=True)
    
    # Timer features
    daily_chat_seconds = db.Column(db.Integer, default=0)
    last_reset_date = db.Column(db.Date, nullable=True)
    total_chat_seconds = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship('Message', backref='user', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='user', lazy=True, cascade='all, delete-orphan')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_user = db.Column(db.Boolean, default=True)
    media_type = db.Column(db.String(20), default='text')  # text, image, video
    media_url = db.Column(db.String(500), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    duration_seconds = db.Column(db.Integer, default=0)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    razorpay_order_id = db.Column(db.String(200))
    razorpay_payment_id = db.Column(db.String(200))
    amount = db.Column(db.Integer)
    status = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==================== HELPER FUNCTIONS ====================

def reset_daily_limit(user):
    """Reset daily chat time if it's a new day"""
    today = date.today()
    if user.last_reset_date != today:
        user.daily_chat_seconds = 0
        user.last_reset_date = today
        db.session.commit()

def get_time_remaining(user):
    """Get remaining chat time in seconds"""
    if user.is_premium:
        return float('inf')
    
    reset_daily_limit(user)
    max_seconds = 20 * 60  # 20 minutes
    remaining = max_seconds - user.daily_chat_seconds
    return max(0, remaining)

def format_time(seconds):
    """Convert seconds to MM:SS format"""
    if seconds == float('inf'):
        return "Unlimited"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"

def get_current_pricing():
    """Get current pricing based on user count"""
    total_users = User.query.count()
    if total_users < 50:
        return {
            'price': 89,
            'is_early_bird': True,
            'users_remaining': 50 - total_users,
            'duration_months': 3
        }
    else:
        return {
            'price': 121,
            'is_early_bird': False,
            'users_remaining': 0,
            'duration_months': 1
        }

# ==================== USER LOADER ====================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== AUTH ROUTES ====================

@app.route('/')
@login_required
def home():
    reset_daily_limit(current_user)
    
    time_remaining = get_time_remaining(current_user)
    time_remaining_formatted = format_time(time_remaining)
    
    # Get recent messages
    recent_messages = Message.query.filter_by(user_id=current_user.id)\
        .order_by(Message.timestamp.desc()).limit(50).all()
    recent_messages.reverse()
    
    return render_template('index.html',
                         username=current_user.username,
                         is_premium=current_user.is_premium,
                         premium_expiry=current_user.premium_expiry,
                         time_remaining=time_remaining,
                         time_remaining_formatted=time_remaining_formatted,
                         messages=recent_messages)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            data = request.get_json()
            username = data.get('username')
            email = data.get('email')
            password = data.get('password')
            
            # Quick validation
            if not username or not email or not password:
                return jsonify({'error': 'All fields required'}), 400
            
            # Check existing (single query)
            existing = User.query.filter(
                (User.email == email) | (User.username == username)
            ).first()
            
            if existing:
                if existing.email == email:
                    return jsonify({'error': 'Email already exists'}), 400
                else:
                    return jsonify({'error': 'Username already exists'}), 400
            
            # Faster hashing with fewer iterations
            hashed_password = generate_password_hash(
                password, 
                method='pbkdf2:sha256', 
                salt_length=8
            )
            
            # Check early bird status
            total_users = User.query.count()
            signup_number = total_users + 1
            is_early_bird = signup_number <= 50
            
            new_user = User(
                username=username,
                email=email,
                password=hashed_password,
                signup_number=signup_number,
                is_early_bird=is_early_bird,
                last_reset_date=date.today()
            )
            
            db.session.add(new_user)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'is_early_bird': is_early_bird,
                'signup_number': signup_number
            })
        
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            data = request.get_json()
            email = data.get('email')
            password = data.get('password')
            
            if not email or not password:
                return jsonify({'error': 'All fields required'}), 400
            
            user = User.query.filter_by(email=email).first()
            
            if user and check_password_hash(user.password, password):
                login_user(user, remember=True, duration=timedelta(days=7))
                return jsonify({'success': True})
            
            return jsonify({'error': 'Invalid credentials'}), 401
        
        except Exception as e:
            return jsonify({'error': 'Login failed'}), 500
    
    return render_template('login.html')


@app.route("/reset-db-secret", methods=["GET"])
def reset_db_secret():
    try:
        from app import db
        db.drop_all()
        db.create_all()
        return "✅ Database reset successfully!", 200
    except Exception as e:
        return f"❌ Error: {e}", 500


# ==================== CHAT API ====================

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    start_time = datetime.utcnow()
    
    reset_daily_limit(current_user)
    time_remaining = get_time_remaining(current_user)
    
    if time_remaining <= 0 and not current_user.is_premium:
        return jsonify({
            'response': '⏰ Daily 20-minute limit reached! Upgrade to Premium for unlimited chat.',
            'limit_reached': True
        })
    
    user_message = request.json.get('message')
    
    try:
        # Save user message
        user_msg = Message(user_id=current_user.id, message=user_message, is_user=True)
        db.session.add(user_msg)
        
        # Get AI response
        response = model.generate_content(user_message)
        ai_response = response.text
        
        # Calculate duration
        end_time = datetime.utcnow()
        duration = int((end_time - start_time).total_seconds())
        
        # Update user's chat time
        if not current_user.is_premium:
            current_user.daily_chat_seconds += duration
        current_user.total_chat_seconds += duration
        
        # Save AI response
        ai_msg = Message(
            user_id=current_user.id,
            message=ai_response,
            is_user=False,
            duration_seconds=duration
        )
        db.session.add(ai_msg)
        db.session.commit()
        
        time_remaining = get_time_remaining(current_user)
        
        return jsonify({
            'response': ai_response,
            'time_remaining': time_remaining,
            'time_remaining_formatted': format_time(time_remaining),
            'duration': duration
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'response': f'Error: {str(e)}'}), 500

# ==================== PAYMENT ROUTES ====================

@app.route('/create-order', methods=['POST'])
@login_required
def create_order():
    try:
        pricing = get_current_pricing()
        amount = pricing['price'] * 100
        
        order = razorpay_client.order.create({
            'amount': amount,
            'currency': 'INR',
            'payment_capture': 1
        })
        
        payment = Payment(
            user_id=current_user.id,
            razorpay_order_id=order['id'],
            amount=pricing['price'],
            status='created'
        )
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({
            'order_id': order['id'],
            'amount': amount,
            'key_id': os.getenv('RAZORPAY_KEY_ID'),
            'pricing_info': pricing
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/payment-success', methods=['POST'])
@login_required
def payment_success():
    try:
        data = request.json
        payment_id = data.get('razorpay_payment_id')
        order_id = data.get('razorpay_order_id')
        
        payment = Payment.query.filter_by(razorpay_order_id=order_id).first()
        if payment:
            payment.razorpay_payment_id = payment_id
            payment.status = 'success'
            
            pricing = get_current_pricing()
            duration_months = pricing['duration_months']
            
            current_user.is_premium = True
            current_user.premium_price = pricing['price']
            current_user.premium_expiry = datetime.utcnow() + timedelta(days=30 * duration_months)
            
            db.session.commit()
            
            return jsonify({'success': True, 'pricing_info': pricing})
        
        return jsonify({'error': 'Payment record not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== HISTORY ROUTES ====================

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
    total_time = format_time(current_user.total_chat_seconds)
    
    return render_template('history.html',
                         grouped_messages=dict(grouped_messages),
                         total_chats=total_chats,
                         total_time=total_time,
                         username=current_user.username)

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
    return jsonify({'success': True})

# ==================== ADMIN ROUTES ====================

@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.email not in ADMIN_EMAILS:
        return redirect(url_for('home'))
    
    total_users = User.query.count()
    premium_users = User.query.filter_by(is_premium=True).count()
    free_users = total_users - premium_users
    early_bird_users = User.query.filter_by(is_early_bird=True).count()
    
    total_revenue = db.session.query(db.func.sum(Payment.amount)).filter_by(status='success').scalar() or 0
    
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_payments = Payment.query.filter_by(status='success').order_by(Payment.created_at.desc()).limit(10).all()
    
    pricing = get_current_pricing()
    
    return render_template('admin.html',
                         total_users=total_users,
                         premium_users=premium_users,
                         free_users=free_users,
                         early_bird_users=early_bird_users,
                         total_revenue=total_revenue,
                         recent_users=recent_users,
                         recent_payments=recent_payments,
                         pricing=pricing)

@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.email not in ADMIN_EMAILS:
        return redirect(url_for('home'))
    
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/make-premium/<int:user_id>', methods=['POST'])
@login_required
def make_premium(user_id):
    if current_user.email not in ADMIN_EMAILS:
        return jsonify({'error': 'Unauthorized'}), 403
    
    user = User.query.get_or_404(user_id)
    user.is_premium = True
    user.premium_expiry = datetime.utcnow() + timedelta(days=30)
    db.session.commit()
    
    return jsonify({'success': True})

# ==================== RUN APP ====================

if __name__ == '__main__':
    with app.app_context():
        # Create tables if not exist
        db.create_all()
        
        # Add missing columns to existing tables
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            
            # Check if new columns exist in User table
            user_columns = [col['name'] for col in inspector.get_columns('user')]
            
            # Add missing columns
            with db.engine.connect() as conn:
                if 'is_early_bird' not in user_columns:
                    conn.execute(text('ALTER TABLE user ADD COLUMN is_early_bird BOOLEAN DEFAULT 0'))
                    conn.commit()
                
                if 'signup_number' not in user_columns:
                    conn.execute(text('ALTER TABLE user ADD COLUMN signup_number INTEGER'))
                    conn.commit()
                
                if 'daily_chat_seconds' not in user_columns:
                    conn.execute(text('ALTER TABLE user ADD COLUMN daily_chat_seconds INTEGER DEFAULT 0'))
                    conn.commit()
                
                if 'last_reset_date' not in user_columns:
                    conn.execute(text('ALTER TABLE user ADD COLUMN last_reset_date DATE'))
                    conn.commit()
                
                if 'total_chat_seconds' not in user_columns:
                    conn.execute(text('ALTER TABLE user ADD COLUMN total_chat_seconds INTEGER DEFAULT 0'))
                    conn.commit()
            
            print("✅ Database migration completed!")
        except Exception as e:
            print(f"⚠️ Migration error (safe to ignore if fresh DB): {e}")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)