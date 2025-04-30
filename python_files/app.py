import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import random
import logging
from flask_wtf.csrf import CSRFProtect
from flask_wtf import FlaskForm
from extensions import db, login_manager
from forms import LoginForm, RegistrationForm, QuestionForm
from models import User, Question, GameSession, QuestionAnswer
from functools import wraps
from sqlalchemy import func, desc, case, and_
from util import admin_required
from admin_dashboard import admin_bp

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Initialize CSRF protection
csrf = CSRFProtect()
csrf.init_app(app)

# Configure the database
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:UsQuiz@localhost:5432/citizenship_quiz'
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize extensions
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'
from extensions import migrate
migrate.init_app(app, db)

# Register blueprints
app.register_blueprint(admin_bp)

@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

# Import models after db initialization
with app.app_context():
    # Create admin user without using the is_admin field
    admin_exists = User.query.filter_by(email='admin@example.com').first()
    if not admin_exists:
        try:
            # We'll create the admin user without setting is_admin field
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash('adminpassword'),
                state='DC'
                # Removed is_admin=True since the column doesn't exist
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully")
        except Exception as e:
            db.session.rollback()
            print(f"Error creating admin user: {e}")
    
    # Add sample questions if none exist
    if db.session.execute(db.select(Question.id)).scalar() is None:
        try:
            from question_importer import import_questions
            import_questions(app)
            print("Questions imported successfully")
        except Exception as e:
            print(f"Error importing questions: {e}")
            logger.info("Admin user created")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Using admin_required decorator from util.py

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('difficulty'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('difficulty'))
        
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            return redirect(url_for('difficulty'))
        flash('Invalid email or password', 'error')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('difficulty'))
        
    form = RegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered', 'error')
            return render_template('register.html', form=form)

        if User.query.filter_by(username=form.username.data).first():
            flash('Username already taken', 'error')
            return render_template('register.html', form=form)

        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data),
            state=form.state.data
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))

@app.route('/difficulty')
@login_required
def difficulty():
    return render_template('difficulty.html')

@app.route('/quiz/<difficulty>')
@login_required
def quiz(difficulty):
    logger.debug(f"Starting quiz with difficulty: {difficulty}")

    # Clear any existing flash messages from previous quiz
    session.pop('_flashes', None)

    if difficulty not in ['easy', 'medium', 'hard']:
        logger.warning(f"Invalid difficulty level requested: {difficulty}")
        return redirect(url_for('difficulty'))

    try:
        # Get questions appropriate for the user's state and the selected difficulty
        base_query = Question.query.filter_by(difficulty=difficulty)
        
        # Get state-specific questions for user's state
        state_questions = base_query.filter(and_(
            Question.state_specific == True, 
            Question.state == current_user.state
        )).all()
        
        # Get general (non-state-specific) questions
        general_questions = base_query.filter(Question.state_specific == False).all()
        
        logger.debug(f"Found {len(state_questions)} state-specific questions and {len(general_questions)} general questions")
        
        # Use only general questions if there are no state-specific ones
        all_available_questions = general_questions
        
        if len(all_available_questions) < 10:
            logger.warning(f"Not enough questions for difficulty {difficulty}. Only {len(all_available_questions)} available")
            flash('Not enough questions available for this difficulty level', 'error')
            return redirect(url_for('difficulty'))

        # Select 10 questions, prioritizing state-specific ones if available
        if len(state_questions) > 0:
            # Include some state-specific questions if available
            state_count = min(3, len(state_questions))
            selected_state = random.sample(state_questions, state_count)
            selected_general = random.sample(general_questions, 10 - state_count)
            selected_questions = selected_state + selected_general
        else:
            # Otherwise use only general questions
            selected_questions = random.sample(all_available_questions, 10)
        
        random.shuffle(selected_questions)
        question_ids = [q.id for q in selected_questions]
        
        session['questions'] = question_ids
        session['current_question'] = 0
        session['score'] = 0
        session['correct_answers'] = 0
        session['incorrect_answers'] = 0
        session['difficulty'] = difficulty
        session['start_time'] = datetime.utcnow().timestamp()
        session['question_data'] = []  # Store data about each question for analytics
        
        # Create a game session at the start of the quiz
        now = datetime.utcnow()
        game_session = GameSession(
            user_id=current_user.id,
            difficulty=difficulty,
            score=0,
            correct_answers=0,
            incorrect_answers=0,
            time_taken=0,
            started_at=now,
            completed_at=now,
            questions_answered=0,
            question_data=json.dumps(question_ids)
        )
        db.session.add(game_session)
        db.session.commit()
        
        # Store the game session ID in the session
        session['game_session_id'] = game_session.id

        first_question = Question.query.get(session['questions'][0])
        if not first_question:
            logger.error("Could not fetch first question")
            flash('Error loading question', 'error')
            return redirect(url_for('difficulty'))

        # Create a form for CSRF protection
        form = FlaskForm()
        
        # Set timer duration based on difficulty
        timer_duration = 60 if difficulty == 'easy' else 30 if difficulty == 'medium' else 15

        return render_template('quiz.html', 
                          question=first_question,
                          question_number=1,
                          total_questions=10,
                          difficulty=difficulty,
                          timer_duration=timer_duration,
                          form=form)

    except Exception as e:
        logger.error(f"Error in quiz route: {str(e)}")
        flash('An error occurred while loading the quiz', 'error')
        return redirect(url_for('difficulty'))

@app.route('/add_time', methods=['POST'])
@login_required
def add_time():
    try:
        if current_user.points >= 20:
            try:
                current_user.points -= 20
                db.session.commit()
                return jsonify({
                    'success': True,
                    'message': 'Added 10 seconds to timer!',
                    'points': current_user.points
                })
            except Exception as e:
                logger.error(f"Error in add_time route: {str(e)}")
                db.session.rollback()
                return jsonify({
                    'success': False,
                    'message': 'Server error while adding time'
                }), 500
        else:
            return jsonify({
                'success': False,
                'message': 'Not enough points to add time'
            }), 400
    except Exception as e:
        logger.error(f"Error in add_time route: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Server error while adding time'
        }), 500

@app.route('/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    try:
        form = FlaskForm()  # Create CSRF form
        if not form.validate():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'error': 'Invalid form submission'
                }), 400
            flash('Invalid form submission', 'error')
            return redirect(url_for('quiz', difficulty=session['difficulty']))

        skipped = request.form.get('skipped') == 'true'
        timer_expired = request.form.get('timer_expired') == 'true'

        current_question_index = session.get('current_question', 0)
        question_id = session['questions'][current_question_index]
        question = Question.query.get(question_id)

        if not question:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'error': 'Error loading question'
                }), 400
            flash('Error loading question', 'error')
            return redirect(url_for('difficulty'))

        # Track correct/incorrect answers and update points
        answer = request.form.get('answer')
        is_correct = False
        
        # Calculate time taken on this question
        current_time = datetime.utcnow().timestamp()
        question_start_time = session.get('question_start_time', session.get('start_time'))
        time_taken = int(current_time - question_start_time)
        
        # Store the start time for the next question
        session['question_start_time'] = current_time

        question_data = {
            'question_id': question.id,
            'time_taken': time_taken,
            'skipped': skipped,
            'timer_expired': timer_expired
        }

        if timer_expired:
            flash('Time Ran Out', 'error')
            session['incorrect_answers'] = session.get('incorrect_answers', 0) + 1
            question_data['is_correct'] = False
            question_data['answer'] = None
            
            try:
                # Update question analytics for timer expiration
                question.total_answers += 1
                question.timer_expired_count += 1
                
                # Create question answer record for timer expiration
                question_answer = QuestionAnswer(
                    question_id=question.id,
                    user_id=current_user.id,
                    game_session_id=session.get('game_session_id'),
                    answer=None,
                    is_correct=False,
                    timer_expired=True,
                    time_taken=time_taken
                )
                db.session.add(question_answer)
                db.session.commit()
            except Exception as e:
                logger.error(f"Error processing timer expiration: {str(e)}")
                db.session.rollback()
        elif skipped:
            if current_user.points >= 50:
                try:
                    current_user.points -= 50
                    db.session.commit()
                    flash('Question skipped successfully', 'success')
                    question_data['is_correct'] = None
                    question_data['answer'] = None
                except Exception as e:
                    logger.error(f"Error processing skip: {str(e)}")
                    db.session.rollback()
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({
                            'error': 'Error processing skip'
                        }), 500
                    flash('Error processing skip', 'error')
                    return redirect(url_for('quiz', difficulty=session['difficulty']))
            else:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'error': 'Not enough points to skip'
                    }), 400
                flash('Not enough points to skip', 'error')
                return redirect(url_for('quiz', difficulty=session['difficulty']))
        else:
            if not answer:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'error': 'Please select an answer'
                    }), 400
                
                # Get the current question to display again when no answer is selected
                current_question = Question.query.get(question_id)
                next_form = FlaskForm()
                flash('Please select an answer', 'error')
                
                # Set timer duration based on difficulty
                timer_duration = 60 if session['difficulty'] == 'easy' else 30 if session['difficulty'] == 'medium' else 15
                
                return render_template('quiz.html', 
                                   question=current_question,
                                   question_number=current_question_index + 1,
                                   total_questions=10,
                                   difficulty=session['difficulty'],
                                   timer_duration=timer_duration,
                                   form=next_form)

            # Clean and normalize both answers for comparison
            submitted_answer = answer.strip() if answer else ''

            # Find the full option text that matches the correct answer
            correct_option = None
            for option in question.options:
                if option.strip() == question.correct_answer.strip():
                    correct_option = option
                    break

            if not correct_option:
                logger.error(f"Could not find matching option for correct answer: {question.correct_answer}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'error': 'Error validating answer'
                    }), 400
                flash('Error validating answer', 'error')
                return redirect(url_for('quiz', difficulty=session['difficulty']))

            # Check if the submitted answer matches the correct option
            is_correct = submitted_answer == correct_option

            try:
                # Update question analytics
                question.total_answers += 1
                if is_correct:
                    question.correct_answers += 1
                
                # Update average time for this question
                if question.avg_time == 0:
                    question.avg_time = time_taken
                else:
                    question.avg_time = (question.avg_time + time_taken) / 2
                
                # Create question answer record
                question_answer = QuestionAnswer(
                    question_id=question.id,
                    user_id=current_user.id,
                    game_session_id=session.get('game_session_id'),  # Use the game session ID created at quiz start
                    answer=submitted_answer if not skipped else None,
                    is_correct=is_correct if not skipped else None,
                    time_taken=time_taken
                )
                db.session.add(question_answer)
                
                if is_correct:
                    points = {'easy': 10, 'medium': 25, 'hard': 50}
                    earned_points = points[session['difficulty']]
                    session['score'] = session.get('score', 0) + earned_points
                    current_user.points = current_user.points + earned_points
                    session['correct_answers'] = session.get('correct_answers', 0) + 1
                    db.session.commit()
                    flash(f'Correct! You earned {earned_points} points!', 'success')
                else:
                    session['incorrect_answers'] = session.get('incorrect_answers', 0) + 1
                    db.session.commit()
                    flash('Incorrect Answer', 'error')

                question_data['is_correct'] = is_correct
                question_data['answer'] = submitted_answer

            except Exception as e:
                logger.error(f"Error processing answer: {str(e)}")
                db.session.rollback()
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'error': 'Error processing your answer'
                    }), 500
                flash('Error processing your answer', 'error')
                return redirect(url_for('quiz', difficulty=session['difficulty']))

        # Add question data to session for analytics
        question_data_list = session.get('question_data', [])
        question_data_list.append(question_data)
        session['question_data'] = question_data_list
        
        session['current_question'] += 1

        # Check if quiz is complete
        if session['current_question'] >= 10:
            try:
                end_time = datetime.utcnow().timestamp()
                time_taken = int(end_time - session['start_time'])

                # Update the existing game session
                game_session_id = session.get('game_session_id')
                if game_session_id:
                    game_session = GameSession.query.get(game_session_id)
                    if game_session:
                        game_session.score = session.get('score', 0)
                        game_session.correct_answers = session.get('correct_answers', 0)
                        game_session.incorrect_answers = session.get('incorrect_answers', 0)
                        game_session.time_taken = time_taken
                        game_session.completed_at = datetime.fromtimestamp(end_time)
                        game_session.questions_answered = 10
                        game_session.question_data = json.dumps(session.get('question_data', []))
                        db.session.commit()
                
                db.session.commit()
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'redirect': url_for('results', 
                                          score=session.get('score', 0),
                                          correct=session.get('correct_answers', 0),
                                          incorrect=session.get('incorrect_answers', 0),
                                          time=time_taken,
                                          difficulty=session['difficulty'])
                    })
                
                return redirect(url_for('results', 
                                     score=session.get('score', 0),
                                     correct=session.get('correct_answers', 0),
                                     incorrect=session.get('incorrect_answers', 0),
                                     time=time_taken,
                                     difficulty=session['difficulty']))
                                     
            except Exception as e:
                logger.error(f"Error saving game session: {str(e)}")
                db.session.rollback()
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'error': 'Error saving game session'
                    }), 500
                flash('Error saving your results', 'error')
                return redirect(url_for('difficulty'))
        else:
            # Load next question
            next_question = Question.query.get(session['questions'][session['current_question']])
            if not next_question:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'error': 'Error loading next question'
                    }), 500
                flash('Error loading next question', 'error')
                return redirect(url_for('difficulty'))
            
            next_form = FlaskForm()
            
            # We're no longer using AJAX for submitting answers as it causes issues
            # Instead, we'll use standard form submission to avoid flash message duplication
            # and question extraction errors
            
            # For non-AJAX requests, render the full page
            # Set timer duration based on difficulty
            timer_duration = 60 if session['difficulty'] == 'easy' else 30 if session['difficulty'] == 'medium' else 15
            
            return render_template('quiz.html', 
                               question=next_question,
                               question_number=session['current_question'] + 1,
                               total_questions=10,
                               difficulty=session['difficulty'],
                               timer_duration=timer_duration,
                               form=next_form)
    
    except Exception as e:
        logger.error(f"Unexpected error in submit_answer: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'error': 'An unexpected error occurred'
            }), 500
        flash('An unexpected error occurred', 'error')
        return redirect(url_for('difficulty'))

@app.route('/results')
@login_required
def results():
    try:
        # Clear any flash messages from previous quiz
        session.pop('_flashes', None)
        
        score = request.args.get('score', 0, type=int)
        correct_answers = request.args.get('correct', 0, type=int)
        incorrect_answers = request.args.get('incorrect', 0, type=int)
        time_taken = request.args.get('time', 0, type=int)
        difficulty = request.args.get('difficulty', 'easy')
        
        total_questions = correct_answers + incorrect_answers
        
        return render_template('results.html', 
                            score=score,
                            difficulty=difficulty,
                            total_questions=total_questions,
                            correct_answers=correct_answers,
                            incorrect_answers=incorrect_answers,
                            time_taken=time_taken)
    except Exception as e:
        logger.error(f"Error in results route: {str(e)}")
        flash('Error loading results', 'error')
        return redirect(url_for('difficulty'))

@app.route('/progress')
@login_required
def progress():
    try:
        # Get all game sessions for the current user, ordered by completion time
        game_sessions = GameSession.query.filter_by(user_id=current_user.id).order_by(GameSession.completed_at.desc()).all()
        
        # Calculate statistics
        stats = {
            'total_games': len(game_sessions),
            'highest_score': 0,
            'lowest_score': float('inf') if game_sessions else 0,
            'total_correct': 0,
            'total_incorrect': 0,
            'avg_time': 0
        }
        
        total_time = 0
        
        for session in game_sessions:
            stats['total_correct'] += session.correct_answers
            stats['total_incorrect'] += session.incorrect_answers
            total_time += session.time_taken
            
            if session.score > stats['highest_score']:
                stats['highest_score'] = session.score
                
            if session.score < stats['lowest_score']:
                stats['lowest_score'] = session.score
        
        if stats['total_games'] > 0:
            stats['avg_time'] = total_time / stats['total_games']
        
        return render_template('progress.html', 
                            game_sessions=game_sessions,
                            stats=stats)
    
    except Exception as e:
        logger.error(f"Error in progress route: {str(e)}")
        flash('Error loading progress data', 'error')
        return redirect(url_for('difficulty'))

# Admin routes moved to admin_dashboard.py blueprint

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
