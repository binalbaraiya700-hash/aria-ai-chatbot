from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import google.generativeai as genai
import razorpay
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Configure Gemini AI
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    api_key = "PASTE_YOUR_API_KEY_HERE"  # Fallback
genai.configure(api_key=api_key)

try:
    model = genai.GenerativeModel('gemini-2.0-flash')
except:
    model = genai.GenerativeModel('gemini-2.5-flash')

# Configure Razorpay
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# Premium plan price (in paise - ₹199 = 19900 paise)
PREMIUM_PRICE = 19900

# ==================== DATABASE MODELS ====================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_premium = db.Column(db.Boolean, default=False)
    premium_expiry = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    messages = db.relationship('Message', backref='user', lazy=True)
    payments = db.relationship('Payment', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_today_message_count(self):
        today = datetime.utcnow().date()
        return Message.query.filter(
            Message.user_id == self.id,
            db.func.date(Message.timestamp) == today
        ).count()
    
    def can_send_message(self):
        # Check if premium is active
        if self.is_premium:
            if self.premium_expiry and self.premium_expiry > datetime.utcnow():
                return True
            else:
                # Premium expired
                self.is_premium = False
                db.session.commit()
                return self.get_today_message_count() < 10
        return self.get_today_message_count() < 10
    
    def activate_premium(self, duration_days=30):
        self.is_premium = True
        self.premium_expiry = datetime.utcnow() + timedelta(days=duration_days)
        db.session.commit()


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    response_text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    razorpay_order_id = db.Column(db.String(100), unique=True, nullable=False)
    razorpay_payment_id = db.Column(db.String(100), nullable=True)
    amount = db.Column(db.Integer, nullable=False)  # in paise
    status = db.Column(db.String(20), default='created')  # created, paid, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)


# ==================== LOGIN MANAGER ====================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ==================== ROUTES ====================

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('chat_page'))
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('chat_page'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not username or not email or not password:
            flash('All fields are required!', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'error')
            return render_template('register.html')
        
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('chat_page'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('chat_page'))
        else:
            flash('Invalid email or password!', 'error')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))


@app.route('/chat')
@login_required
def chat_page():
    messages_today = current_user.get_today_message_count()
    messages_left = 10 - messages_today if not current_user.is_premium else "Unlimited"
    
    return render_template('index.html', 
                         username=current_user.username,
                         is_premium=current_user.is_premium,
                         messages_left=messages_left,
                         premium_expiry=current_user.premium_expiry,
                         razorpay_key=RAZORPAY_KEY_ID)


@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    if not current_user.can_send_message():
        return jsonify({
            'error': 'Daily message limit reached! Upgrade to Premium for unlimited messages.',
            'limit_reached': True
        }), 429
    
    user_message = request.json.get('message')
    
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    
    try:
        response = model.generate_content(user_message)
        ai_response = response.text
        
        new_message = Message(
            user_id=current_user.id,
            message_text=user_message,
            response_text=ai_response
        )
        db.session.add(new_message)
        db.session.commit()
        
        messages_left = 10 - current_user.get_today_message_count()
        if current_user.is_premium:
            messages_left = "Unlimited"
        
        return jsonify({
            'response': ai_response,
            'messages_left': messages_left
        })
    
    except Exception as e:
        return jsonify({'error': f'Error: {str(e)}'}), 500


@app.route('/api/user-info')
@login_required
def user_info():
    return jsonify({
        'username': current_user.username,
        'email': current_user.email,
        'is_premium': current_user.is_premium,
        'messages_today': current_user.get_today_message_count(),
        'messages_left': 10 - current_user.get_today_message_count() if not current_user.is_premium else "Unlimited",
        'premium_expiry': current_user.premium_expiry.isoformat() if current_user.premium_expiry else None
    })


# ==================== PAYMENT ROUTES ====================

@app.route('/create-order', methods=['POST'])
@login_required
def create_order():
    try:
        # Create Razorpay order
        order_data = {
            'amount': PREMIUM_PRICE,  # ₹199 in paise
            'currency': 'INR',
            'payment_capture': 1
        }
        
        razorpay_order = razorpay_client.order.create(data=order_data)
        
        # Save order in database
        payment = Payment(
            user_id=current_user.id,
            razorpay_order_id=razorpay_order['id'],
            amount=PREMIUM_PRICE,
            status='created'
        )
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({
            'order_id': razorpay_order['id'],
            'amount': PREMIUM_PRICE,
            'currency': 'INR',
            'key': RAZORPAY_KEY_ID
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/verify-payment', methods=['POST'])
@login_required
def verify_payment():
    try:
        data = request.json
        
        # Verify signature
        params_dict = {
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        }
        
        razorpay_client.utility.verify_payment_signature(params_dict)
        
        # Update payment record
        payment = Payment.query.filter_by(razorpay_order_id=data['razorpay_order_id']).first()
        
        if payment:
            payment.razorpay_payment_id = data['razorpay_payment_id']
            payment.status = 'paid'
            payment.paid_at = datetime.utcnow()
            db.session.commit()
            
            # Activate premium
            current_user.activate_premium(duration_days=30)
            
            return jsonify({
                'success': True,
                'message': 'Payment successful! Premium activated!'
            })
        
        return jsonify({'error': 'Payment record not found'}), 404
    
    except Exception as e:
        # Payment verification failed
        payment = Payment.query.filter_by(razorpay_order_id=data.get('razorpay_order_id')).first()
        if payment:
            payment.status = 'failed'
            db.session.commit()
        
        return jsonify({'error': 'Payment verification failed', 'details': str(e)}), 400


@app.route('/payment-history')
@login_required
def payment_history():
    payments = Payment.query.filter_by(user_id=current_user.id).order_by(Payment.created_at.desc()).all()
    return render_template('payment_history.html', payments=payments)


# ==================== INITIALIZE DATABASE ====================

with app.app_context():
    db.create_all()

# ==================== ADMIN ROUTES ====================

# Simple admin check - in production, use proper authentication
ADMIN_EMAILS = ['binalbaraiya700@gmail.com']  # Add your email here

def is_admin():
    return current_user.is_authenticated and current_user.email in ADMIN_EMAILS

@app.route('/admin')
@login_required
def admin_dashboard():
    if not is_admin():
        flash('Access denied! Admin only.', 'error')
        return redirect(url_for('chat_page'))
    
    # Statistics
    total_users = User.query.count()
    premium_users = User.query.filter_by(is_premium=True).count()
    free_users = total_users - premium_users
    
    total_messages = Message.query.count()
    total_payments = Payment.query.filter_by(status='paid').count()
    total_revenue = Payment.query.filter_by(status='paid').with_entities(
        db.func.sum(Payment.amount)
    ).scalar() or 0
    
    # Convert paise to rupees
    total_revenue = total_revenue / 100
    
    # Recent users
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    
    # Recent payments
    recent_payments = Payment.query.filter_by(status='paid').order_by(
        Payment.paid_at.desc()
    ).limit(10).all()
    
    # Daily stats (last 7 days)
    from datetime import datetime, timedelta
    today = datetime.utcnow().date()
    daily_stats = []
    
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        users_count = User.query.filter(
            db.func.date(User.created_at) == date
        ).count()
        
        payments_count = Payment.query.filter(
            Payment.status == 'paid',
            db.func.date(Payment.paid_at) == date
        ).count()
        
        daily_stats.append({
            'date': date.strftime('%d %b'),
            'users': users_count,
            'payments': payments_count
        })
    
    return render_template('admin.html',
                         total_users=total_users,
                         premium_users=premium_users,
                         free_users=free_users,
                         total_messages=total_messages,
                         total_payments=total_payments,
                         total_revenue=total_revenue,
                         recent_users=recent_users,
                         recent_payments=recent_payments,
                         daily_stats=daily_stats)


@app.route('/admin/users')
@login_required
def admin_users():
    if not is_admin():
        flash('Access denied! Admin only.', 'error')
        return redirect(url_for('chat_page'))
    
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users)


@app.route('/admin/make-premium/<int:user_id>')
@login_required
def make_premium(user_id):
    if not is_admin():
        flash('Access denied! Admin only.', 'error')
        return redirect(url_for('chat_page'))
    
    user = User.query.get_or_404(user_id)
    user.activate_premium(duration_days=30)
    flash(f'{user.username} is now Premium for 30 days!', 'success')
    return redirect(url_for('admin_users'))

# ==================== CHAT HISTORY ROUTES ====================

@app.route('/history')
@login_required
def chat_history():
    # Get all messages for current user, grouped by date
    messages = Message.query.filter_by(user_id=current_user.id).order_by(
        Message.timestamp.desc()
    ).all()
    
    # Group by date
    from collections import defaultdict
    grouped_messages = defaultdict(list)
    
    for msg in messages:
        date_key = msg.timestamp.strftime('%d %b %Y')
        grouped_messages[date_key].append(msg)
    
    total_chats = len(messages)
    return render_template('history.html', 
                     grouped_messages=dict(grouped_messages),
                     total_chats=total_chats,
                     username=current_user.username)


@app.route('/api/delete-chat/<int:message_id>', methods=['POST'])
@login_required
def delete_chat(message_id):
    message = Message.query.get_or_404(message_id)
    
    # Check if message belongs to current user
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

# ==================== RUN APP ====================

if __name__ == '__main__':
    app.run(debug=True)