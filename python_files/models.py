from datetime import datetime
from flask_login import UserMixin
from extensions import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    state = db.Column(db.String(2), nullable=False)
    points = db.Column(db.Integer, default=0)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    game_sessions = db.relationship('GameSession', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    options = db.Column(db.JSON, nullable=False)
    correct_answer = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(10), nullable=False)
    state_specific = db.Column(db.Boolean, default=False)
    state = db.Column(db.String(2), nullable=True)
    
    # Analytics columns
    total_answers = db.Column(db.Integer, default=0)
    correct_answers = db.Column(db.Integer, default=0)
    timer_expired_count = db.Column(db.Integer, default=0)  # Count of times the timer expired
    avg_time = db.Column(db.Float, default=0.0)

    @property
    def correct_percentage(self):
        if self.total_answers > 0:
            return (self.correct_answers / self.total_answers) * 100
        return 0
    
    @property
    def timer_expired_percentage(self):
        if self.total_answers > 0:
            return (self.timer_expired_count / self.total_answers) * 100
        return 0

    def __repr__(self):
        return f'<Question {self.id}>'

class GameSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    difficulty = db.Column(db.String(10), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    correct_answers = db.Column(db.Integer, default=0)
    incorrect_answers = db.Column(db.Integer, default=0)
    time_taken = db.Column(db.Integer, nullable=False)  # Time taken in seconds
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    questions_answered = db.Column(db.Integer, nullable=False)
    
    # Detailed question data
    question_data = db.Column(db.JSON, nullable=True)

    @property
    def time_taken_formatted(self):
        minutes = self.time_taken // 60
        seconds = self.time_taken % 60
        return f"{minutes}m {seconds}s"

    def __repr__(self):
        return f'<GameSession {self.id}>'

class QuestionAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_session_id = db.Column(db.Integer, db.ForeignKey('game_session.id'), nullable=False)
    answer = db.Column(db.Text, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=False)
    timer_expired = db.Column(db.Boolean, default=False)  # Whether the timer expired for this question
    time_taken = db.Column(db.Integer, nullable=False)  # Time taken in seconds
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    question = db.relationship('Question', backref=db.backref('answers', lazy=True))
    user = db.relationship('User', backref=db.backref('answers', lazy=True))
    game_session = db.relationship('GameSession', backref=db.backref('answers', lazy=True))

    def __repr__(self):
        return f'<QuestionAnswer {self.id}>'
