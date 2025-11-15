from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import secrets
import json
import re
from brain import ARIABrain

# Anthropic Claude API
import anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///aria_database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

# Initialize extensions
db = SQLAlchemy(app)
CORS(app, resources={r"/*": {"origins": "*"}})
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize ARIA Brain
aria_brain = ARIABrain()

# Initialize Anthropic Claude
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', 'your-api-key-here')
try:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
except Exception as e:
    print(f"Anthropic API initialization error: {e}")
    client = None

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    streak = db.Column(db.Integer, default=0)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    messages_count = db.Column(db.Integer, default=0)
    messages_today = db.Column(db.Integer, default=0)
    last_message_date = db.Column(db.Date, default=datetime.utcnow().date)
    quiz_score = db.Column(db.Integer, default=0)
    games_played = db.Column(db.Integer, default=0)
    
    # Memory storage
    preferences = db.Column(db.Text, default='{}')  # JSON
    learned_topics = db.Column(db.Text, default='[]')  # JSON
    
    chats = db.relationship('Chat', backref='user', lazy=True, cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='user', lazy=True, cascade='all, delete-orphan')
    learning_progress = db.relationship('LearningProgress', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_preferences(self):
        try:
            return json.loads(self.preferences)
        except:
            return {}
    
    def set_preferences(self, prefs):
        self.preferences = json.dumps(prefs)

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.Column(db.String(50), default='general')
    mood = db.Column(db.String(50), default='neutral')
    intent = db.Column(db.String(50), default='conversation')

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    completed = db.Column(db.Boolean, default=False)
    priority = db.Column(db.String(20), default='medium')
    due_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

class LearningProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    topic = db.Column(db.String(100), nullable=False)
    progress = db.Column(db.Integer, default=0)  # 0-100
    quiz_scores = db.Column(db.Text, default='[]')  # JSON array
    last_studied = db.Column(db.DateTime, default=datetime.utcnow)
    mastery_level = db.Column(db.String(20), default='beginner')

class GameScore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_name = db.Column(db.String(50), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Create database tables
with app.app_context():
    try:
        db.create_all()
        print("✅ Database tables created successfully")
        
        # Create default admin if not exists
        admin = User.query.filter_by(email='admin@aria.com').first()
        if not admin:
            admin = User(
                username='Admin',
                email='admin@aria.com',
                is_admin=True,
                is_premium=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("✅ Default admin created: admin@aria.com / admin123")
    except Exception as e:
        print(f"❌ Database creation error: {e}")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== ROUTES ====================

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            
            # Update streak
            today = datetime.utcnow().date()
            if user.last_active.date() == today - timedelta(days=1):
                user.streak += 1
            elif user.last_active.date() != today:
                user.streak = 1
            
            user.last_active = datetime.utcnow()
            db.session.commit()
            
            return jsonify({
                'success': True,
                'redirect': '/admin' if user.is_admin else '/'
            })
        
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    
    try:
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
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ==================== PROFILE & SETTINGS ====================

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
            'streak': current_user.streak,
            'messages_count': current_user.messages_count,
            'messages_today': current_user.messages_today,
            'is_premium': current_user.is_premium,
            'is_admin': current_user.is_admin,
            'experience': current_user.experience,
            'interest': current_user.interest,
            'quiz_score': current_user.quiz_score,
            'games_played': current_user.games_played,
            'created_at': current_user.created_at.isoformat()
        }
    })

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def handle_settings():
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'settings': current_user.get_preferences()
        })
    
    try:
        data = request.get_json()
        current_user.set_preferences(data)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== CHAT WITH ARIA BRAIN ====================

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    try:
        data = request.get_json()
        message = data.get('message', '')
        
        if not message:
            return jsonify({'success': False, 'error': 'Message is required'}), 400
        
        # Update message count
        today = datetime.utcnow().date()
        if current_user.last_message_date != today:
            current_user.messages_today = 0
            current_user.last_message_date = today
        
        # Check limits for free users
        if not current_user.is_premium and current_user.messages_today >= 50:
            return jsonify({
                'success': False,
                'error': '🚀 Daily limit reached! Upgrade to Premium for unlimited messages.'
            }), 429
        
        # Process with ARIA Brain
        user_info = {
            'name': current_user.username,
            'preferences': current_user.get_preferences(),
            'level': current_user.experience,
            'interest': current_user.interest
        }
        
        context = aria_brain.process_message(message, user_info)
        
        # Generate AI response with Claude
        if client:
            try:
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2000,
                    system=context['system_prompt'],
                    messages=[
                        {"role": "user", "content": message}
                    ]
                )
                ai_response = response.content[0].text
            except Exception as e:
                ai_response = f"AI temporarily unavailable. Error: {str(e)}"
        else:
            ai_response = aria_brain.generate_response(
                "I'm currently in offline mode, but I'm here to help!",
                tone='friendly',
                user_mood=context['mood']
            )
        
        # Save chat with metadata
        chat_entry = Chat(
            user_id=current_user.id,
            message=message,
            response=ai_response,
            mood=context['mood'],
            intent=context['intent']['primary_intent']
        )
        db.session.add(chat_entry)
        
        # Update user stats
        current_user.messages_count += 1
        current_user.messages_today += 1
        current_user.xp += 10
        current_user.last_active = datetime.utcnow()
        
        # Level up logic
        xp_needed = current_user.level * 100
        level_up = False
        if current_user.xp >= xp_needed:
            current_user.level += 1
            current_user.xp = 0
            level_up = True
        
        # Store in ARIA brain memory
        aria_brain.add_conversation(message, ai_response)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'response': ai_response,
            'xp': current_user.xp,
            'level': current_user.level,
            'level_up': level_up,
            'mood': context['mood'],
            'intent': context['intent']['primary_intent'],
            'messages_left': 50 - current_user.messages_today if not current_user.is_premium else -1
        })
    
    except Exception as e:
        app.logger.error(f"Chat error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== LEARNING MODULE ====================

@app.route('/learning')
@login_required
def learning():
    return render_template('learning.html')

@app.route('/api/learning/topics')
@login_required
def get_learning_topics():
    topics = [
        {'id': 'aviation_basics', 'name': 'Aviation Basics', 'icon': '✈️'},
        {'id': 'python', 'name': 'Python Programming', 'icon': '🐍'},
        {'id': 'aerodynamics', 'name': 'Aerodynamics', 'icon': '🌪️'},
        {'id': 'navigation', 'name': 'Navigation', 'icon': '🧭'},
        {'id': 'weather', 'name': 'Weather Systems', 'icon': '⛈️'},
        {'id': 'javascript', 'name': 'JavaScript', 'icon': '💻'}
    ]
    return jsonify({'success': True, 'topics': topics})

@app.route('/api/learning/progress/<topic>')
@login_required
def get_learning_progress(topic):
    progress = LearningProgress.query.filter_by(
        user_id=current_user.id,
        topic=topic
    ).first()
    
    if not progress:
        progress = LearningProgress(user_id=current_user.id, topic=topic)
        db.session.add(progress)
        db.session.commit()
    
    return jsonify({
        'success': True,
        'progress': {
            'topic': progress.topic,
            'progress': progress.progress,
            'mastery_level': progress.mastery_level,
            'last_studied': progress.last_studied.isoformat(),
            'quiz_scores': json.loads(progress.quiz_scores)
        }
    })

@app.route('/api/learning/quiz', methods=['POST'])
@login_required
def submit_quiz():
    try:
        data = request.get_json()
        topic = data.get('topic')
        score = data.get('score', 0)
        
        progress = LearningProgress.query.filter_by(
            user_id=current_user.id,
            topic=topic
        ).first()
        
        if not progress:
            progress = LearningProgress(user_id=current_user.id, topic=topic)
            db.session.add(progress)
        
        # Update scores
        scores = json.loads(progress.quiz_scores)
        scores.append({'score': score, 'date': datetime.utcnow().isoformat()})
        progress.quiz_scores = json.dumps(scores[-10:])  # Keep last 10
        
        # Update progress
        progress.progress = min(100, progress.progress + 10)
        progress.last_studied = datetime.utcnow()
        
        # Update mastery
        avg_score = sum([s['score'] for s in scores[-5:]]) / min(len(scores), 5)
        if avg_score >= 90:
            progress.mastery_level = 'expert'
        elif avg_score >= 70:
            progress.mastery_level = 'advanced'
        elif avg_score >= 50:
            progress.mastery_level = 'intermediate'
        
        # Reward XP
        current_user.xp += score
        current_user.quiz_score += score
        
        db.session.commit()
        
        return jsonify({'success': True, 'xp_earned': score})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== GAMES ====================

@app.route('/games')
@login_required
def games():
    return render_template('games.html')

@app.route('/api/games/score', methods=['POST'])
@login_required
def save_game_score():
    try:
        data = request.get_json()
        game_name = data.get('game_name')
        score = data.get('score', 0)
        
        game_score = GameScore(
            user_id=current_user.id,
            game_name=game_name,
            score=score
        )
        db.session.add(game_score)
        
        current_user.games_played += 1
        current_user.xp += score // 10  # 10 points = 1 XP
        
        db.session.commit()
        
        return jsonify({'success': True, 'xp_earned': score // 10})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/games/leaderboard/<game_name>')
@login_required
def get_leaderboard(game_name):
    scores = GameScore.query.filter_by(game_name=game_name)\
        .order_by(GameScore.score.desc())\
        .limit(10)\
        .all()
    
    return jsonify({
        'success': True,
        'leaderboard': [{
            'username': User.query.get(s.user_id).username,
            'score': s.score,
            'timestamp': s.timestamp.isoformat()
        } for s in scores]
    })

# ==================== TASKS ====================

@app.route('/api/tasks', methods=['GET', 'POST'])
@login_required
def handle_tasks():
    if request.method == 'GET':
        tasks = Task.query.filter_by(user_id=current_user.id).all()
        return jsonify({
            'success': True,
            'tasks': [{
                'id': t.id,
                'title': t.title,
                'description': t.description,
                'completed': t.completed,
                'priority': t.priority,
                'due_date': t.due_date.isoformat() if t.due_date else None,
                'created_at': t.created_at.isoformat()
            } for t in tasks]
        })
    
    try:
        data = request.get_json()
        task = Task(
            user_id=current_user.id,
            title=data.get('title'),
            description=data.get('description', ''),
            priority=data.get('priority', 'medium'),
            due_date=datetime.fromisoformat(data['due_date']) if data.get('due_date') else None
        )
        db.session.add(task)
        db.session.commit()
        return jsonify({'success': True, 'task_id': task.id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tasks/<int:task_id>', methods=['PUT', 'DELETE'])
@login_required
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    if task.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    if request.method == 'DELETE':
        db.session.delete(task)
        db.session.commit()
        return jsonify({'success': True})
    
    try:
        data = request.get_json()
        if 'completed' in data:
            task.completed = data['completed']
            if data['completed']:
                task.completed_at = datetime.utcnow()
                current_user.xp += 20  # XP for completing task
        
        if 'title' in data:
            task.title = data['title']
        if 'description' in data:
            task.description = data['description']
        if 'priority' in data:
            task.priority = data['priority']
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== HISTORY ====================

@app.route('/history')
@login_required
def history():
    chats = Chat.query.filter_by(user_id=current_user.id)\
        .order_by(Chat.timestamp.desc())\
        .limit(50)\
        .all()
    return jsonify({
        'success': True,
        'chats': [{
            'message': c.message,
            'response': c.response,
            'timestamp': c.timestamp.isoformat(),
            'mood': c.mood,
            'intent': c.intent
        } for c in chats]
    })

# ==================== ADMIN ====================

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    return render_template('admin.html')

@app.route('/api/admin/stats')
@login_required
def admin_stats():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    total_users = User.query.count()
    total_chats = Chat.query.count()
    total_tasks = Task.query.count()
    premium_users = User.query.filter_by(is_premium=True).count()
    
    return jsonify({
        'success': True,
        'stats': {
            'total_users': total_users,
            'total_chats': total_chats,
            'total_tasks': total_tasks,
            'premium_users': premium_users
        }
    })

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(e):
    return render_template('login.html'), 404

@app.errorhandler(500)
def internal_error(e):
    app.logger.error(f"500 error: {e}")
    return jsonify({'error': 'Internal server error'}), 500

# ==================== RUN SERVER ====================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)