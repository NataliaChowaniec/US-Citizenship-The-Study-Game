import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, User, Question, GameSession, QuestionAnswer
from sqlalchemy import func, desc, case, and_
import logging
from util import admin_required

# Add a helper function to check if a request is AJAX/XHR
def is_xhr_request(req):
    return req.headers.get('X-Requested-With') == 'XMLHttpRequest'

# Create blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

logger = logging.getLogger(__name__)

@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    try:
        # Calculate basic stats
        avg_score = db.session.query(func.avg(GameSession.score)).scalar() 
        if avg_score is None:
            avg_score = 0
        else:
            avg_score = round(float(avg_score), 1)
        
        stats = {
            'total_users': User.query.count(),
            'total_quizzes': GameSession.query.count(),
            'avg_score': avg_score,
            'total_questions': Question.query.count()
        }
        
        # Get questions for each difficulty level for the table
        easy_questions = Question.query.filter_by(difficulty='easy').order_by(
            Question.id.asc()  # Order by ID to show questions in the order they were added
        ).all()
        
        medium_questions = Question.query.filter_by(difficulty='medium').order_by(
            Question.id.asc()
        ).all()
        
        hard_questions = Question.query.filter_by(difficulty='hard').order_by(
            Question.id.asc()
        ).all()
        
        # Prepare chart data by difficulty level
        all_questions = Question.query.order_by(Question.id).all()
        
        # Group questions by difficulty
        easy_chart_questions = [q for q in all_questions if q.difficulty == 'easy']
        medium_chart_questions = [q for q in all_questions if q.difficulty == 'medium']
        hard_chart_questions = [q for q in all_questions if q.difficulty == 'hard']
        
        # Create chart data for each difficulty
        easy_chart_data = {
            'labels': [str(q.id) for q in easy_chart_questions],
            'correct_percentages': [round(q.correct_percentage, 1) if q.total_answers > 0 else 0 for q in easy_chart_questions],
            'incorrect_percentages': [round(100 - q.correct_percentage - q.timer_expired_percentage, 1) if q.total_answers > 0 else 0 for q in easy_chart_questions],
            'timer_expired_percentages': [round(q.timer_expired_percentage, 1) if q.total_answers > 0 else 0 for q in easy_chart_questions]
        }
        
        medium_chart_data = {
            'labels': [str(q.id) for q in medium_chart_questions],
            'correct_percentages': [round(q.correct_percentage, 1) if q.total_answers > 0 else 0 for q in medium_chart_questions],
            'incorrect_percentages': [round(100 - q.correct_percentage - q.timer_expired_percentage, 1) if q.total_answers > 0 else 0 for q in medium_chart_questions],
            'timer_expired_percentages': [round(q.timer_expired_percentage, 1) if q.total_answers > 0 else 0 for q in medium_chart_questions]
        }
        
        hard_chart_data = {
            'labels': [str(q.id) for q in hard_chart_questions],
            'correct_percentages': [round(q.correct_percentage, 1) if q.total_answers > 0 else 0 for q in hard_chart_questions],
            'incorrect_percentages': [round(100 - q.correct_percentage - q.timer_expired_percentage, 1) if q.total_answers > 0 else 0 for q in hard_chart_questions],
            'timer_expired_percentages': [round(q.timer_expired_percentage, 1) if q.total_answers > 0 else 0 for q in hard_chart_questions]
        }
        
        # Create chart data for all questions
        all_chart_data = {
            'labels': [str(q.id) for q in all_questions],
            'correct_percentages': [round(q.correct_percentage, 1) if q.total_answers > 0 else 0 for q in all_questions],
            'incorrect_percentages': [round(100 - q.correct_percentage - q.timer_expired_percentage, 1) if q.total_answers > 0 else 0 for q in all_questions],
            'timer_expired_percentages': [round(q.timer_expired_percentage, 1) if q.total_answers > 0 else 0 for q in all_questions]
        }
        
        # Get recent game sessions - show more recent sessions
        recent_sessions = GameSession.query.order_by(GameSession.completed_at.desc()).limit(10).all()
        
        # Get top users by points - show more top users
        top_users = User.query.order_by(User.points.desc()).limit(20).all()
        
        return render_template('admin/dashboard.html',
                            stats=stats,
                            all_chart_data=all_chart_data,
                            easy_chart_data=easy_chart_data,
                            medium_chart_data=medium_chart_data,
                            hard_chart_data=hard_chart_data,
                            recent_sessions=recent_sessions,
                            top_users=top_users,
                            easy_questions=easy_questions,
                            medium_questions=medium_questions,
                            hard_questions=hard_questions,
                            all_questions=all_questions)
    
    except Exception as e:
        logger.error(f"Error in admin dashboard: {str(e)}")
        flash('Error loading dashboard data', 'error')
        return redirect(url_for('index'))

@admin_bp.route('/questions')
@login_required
@admin_required
def questions():
    try:
        page = request.args.get('page', 1, type=int)
        difficulty = request.args.get('difficulty', 'all')
        state_specific = request.args.get('state_specific', 'all')
        state = request.args.get('state', 'all')
        
        per_page = 100  # Increase number of questions per page
        query = Question.query
        
        # Apply filters
        if difficulty != 'all':
            query = query.filter_by(difficulty=difficulty)
            
        if state_specific == 'true':
            query = query.filter_by(state_specific=True)
        elif state_specific == 'false':
            query = query.filter_by(state_specific=False)
            
        if state != 'all':
            query = query.filter_by(state=state)
            
        # Paginate results
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        questions = pagination.items
        total_pages = pagination.pages
        
        # Get list of states for filter dropdown
        states = [
            ('AL', 'Alabama'), ('AK', 'Alaska'), ('AZ', 'Arizona'),
            ('AR', 'Arkansas'), ('CA', 'California'), ('CO', 'Colorado'),
            ('CT', 'Connecticut'), ('DE', 'Delaware'), ('FL', 'Florida'),
            ('GA', 'Georgia'), ('HI', 'Hawaii'), ('ID', 'Idaho'),
            ('IL', 'Illinois'), ('IN', 'Indiana'), ('IA', 'Iowa'),
            ('KS', 'Kansas'), ('KY', 'Kentucky'), ('LA', 'Louisiana'),
            ('ME', 'Maine'), ('MD', 'Maryland'), ('MA', 'Massachusetts'),
            ('MI', 'Michigan'), ('MN', 'Minnesota'), ('MS', 'Mississippi'),
            ('MO', 'Missouri'), ('MT', 'Montana'), ('NE', 'Nebraska'),
            ('NV', 'Nevada'), ('NH', 'New Hampshire'), ('NJ', 'New Jersey'),
            ('NM', 'New Mexico'), ('NY', 'New York'), ('NC', 'North Carolina'),
            ('ND', 'North Dakota'), ('OH', 'Ohio'), ('OK', 'Oklahoma'),
            ('OR', 'Oregon'), ('PA', 'Pennsylvania'), ('RI', 'Rhode Island'),
            ('SC', 'South Carolina'), ('SD', 'South Dakota'), ('TN', 'Tennessee'),
            ('TX', 'Texas'), ('UT', 'Utah'), ('VT', 'Vermont'),
            ('VA', 'Virginia'), ('WA', 'Washington'), ('WV', 'West Virginia'),
            ('WI', 'Wisconsin'), ('WY', 'Wyoming')
        ]
        
        # Prepare JSON data for charts
        questions_json = json.dumps([{
            'id': q.id,
            'difficulty': q.difficulty,
            'total_answers': q.total_answers,
            'correct_answers': q.correct_answers,
            'timeout_count': q.timer_expired_count,
            'avg_time': q.avg_time
        } for q in questions])
        
        return render_template('admin/questions.html',
                            questions=questions,
                            questions_json=questions_json,
                            page=page,
                            total_pages=total_pages,
                            difficulty=difficulty,
                            state_specific=state_specific,
                            state=state,
                            states=states)
    
    except Exception as e:
        logger.error(f"Error in admin questions: {str(e)}")
        flash('Error loading questions', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    try:
        # Force refresh the current user from database
        from extensions import db
        db.session.refresh(current_user)
        
        # Debugging
        print(f"DEBUG - User {current_user.id} admin status: {current_user.is_admin}")
        
        page = request.args.get('page', 1, type=int)
        sort = request.args.get('sort', 'username')
        state = request.args.get('state', 'all')
        is_admin = request.args.get('is_admin', 'all')
        
        query = User.query
        
        if state != 'all':
            query = query.filter_by(state=state)
            
        if is_admin == 'true':
            query = query.filter(User.is_admin == True)
        elif is_admin == 'false':
            query = query.filter(User.is_admin == False)
            
        if sort == 'username':
            query = query.order_by(User.username)
        elif sort == 'created_at':
            query = query.order_by(User.created_at.desc())
        elif sort == 'points':
            query = query.order_by(User.points.desc())
        elif sort == 'game_sessions':
            query = query.outerjoin(GameSession, User.id == GameSession.user_id)\
                   .group_by(User.id)\
                   .order_by(func.count(GameSession.id).desc())
        
        users = query.paginate(page=page, per_page=100, error_out=False)
        
        # Get list of states for filter dropdown
        states = [
            ('AL', 'Alabama'), ('AK', 'Alaska'), ('AZ', 'Arizona'),
            ('AR', 'Arkansas'), ('CA', 'California'), ('CO', 'Colorado'),
            ('CT', 'Connecticut'), ('DE', 'Delaware'), ('FL', 'Florida'),
            ('GA', 'Georgia'), ('HI', 'Hawaii'), ('ID', 'Idaho'),
            ('IL', 'Illinois'), ('IN', 'Indiana'), ('IA', 'Iowa'),
            ('KS', 'Kansas'), ('KY', 'Kentucky'), ('LA', 'Louisiana'),
            ('ME', 'Maine'), ('MD', 'Maryland'), ('MA', 'Massachusetts'),
            ('MI', 'Michigan'), ('MN', 'Minnesota'), ('MS', 'Mississippi'),
            ('MO', 'Missouri'), ('MT', 'Montana'), ('NE', 'Nebraska'),
            ('NV', 'Nevada'), ('NH', 'New Hampshire'), ('NJ', 'New Jersey'),
            ('NM', 'New Mexico'), ('NY', 'New York'), ('NC', 'North Carolina'),
            ('ND', 'North Dakota'), ('OH', 'Ohio'), ('OK', 'Oklahoma'),
            ('OR', 'Oregon'), ('PA', 'Pennsylvania'), ('RI', 'Rhode Island'),
            ('SC', 'South Carolina'), ('SD', 'South Dakota'), ('TN', 'Tennessee'),
            ('TX', 'Texas'), ('UT', 'Utah'), ('VT', 'Vermont'),
            ('VA', 'Virginia'), ('WA', 'Washington'), ('WV', 'West Virginia'),
            ('WI', 'Wisconsin'), ('WY', 'Wyoming')
        ]
        
        # Get game count per user
        user_game_counts = {}
        for user in users:
            user_game_counts[user.id] = GameSession.query.filter_by(user_id=user.id).count()
        
        return render_template('admin/users.html',
                            users=users.items,
                            user_game_counts={u.id: len(u.game_sessions) for u in users.items},
                            page=page,
                            total_pages=users.pages,
                            sort=sort,
                            state=state,
                            is_admin=is_admin,
                            states=states)
    
    except Exception as e:
        logger.error(f"Error in admin users: {str(e)}", exc_info=True)
        flash('Error loading users', 'error')
        return redirect(url_for('admin.dashboard'))
@admin_bp.route('/update_question_difficulty', methods=['POST'])
@login_required
@admin_required
def update_question_difficulty():
    try:
        data = request.get_json()
        question_id = data.get('question_id')
        difficulty = data.get('difficulty')
        
        if not question_id or not difficulty:
            return jsonify({'success': False, 'message': 'Missing required data'})
            
        if difficulty not in ['easy', 'medium', 'hard']:
            return jsonify({'success': False, 'message': 'Invalid difficulty level'})
            
        question = Question.query.get(question_id)
        if not question:
            return jsonify({'success': False, 'message': 'Question not found'})
            
        question.difficulty = difficulty
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Question difficulty updated'})
        
    except Exception as e:
        logger.error(f"Error updating question difficulty: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Server error'})

@admin_bp.route('/update_question_state', methods=['POST'])
@login_required
@admin_required
def update_question_state():
    try:
        data = request.get_json()
        question_id = data.get('question_id')
        state_specific = data.get('state_specific')
        state = data.get('state')
        
        if not question_id or state_specific is None:
            return jsonify({'success': False, 'message': 'Missing required data'})
            
        question = Question.query.get(question_id)
        if not question:
            return jsonify({'success': False, 'message': 'Question not found'})
            
        question.state_specific = state_specific
        if state_specific:
            if not state:
                return jsonify({'success': False, 'message': 'State is required for state-specific questions'})
            question.state = state
        else:
            question.state = None
            
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Question state settings updated'})
        
    except Exception as e:
        logger.error(f"Error updating question state: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Server error'})

@admin_bp.route('/toggle_admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin():
    try:
        user_id = request.form.get('user_id', type=int)
        if not user_id:
            if is_xhr_request(request):
                return jsonify({'success': False, 'message': 'Invalid user ID'})
            flash('Invalid user ID', 'error')
            return redirect(url_for('admin.users'))
            
        user = User.query.get(user_id)
        if not user:
            if is_xhr_request(request):
                return jsonify({'success': False, 'message': 'User not found'})
            flash('User not found', 'error')
            return redirect(url_for('admin.users'))
        
        # Check if this is the user trying to modify their own admin status
        if user.id == current_user.id:
            if is_xhr_request(request):
                return jsonify({'success': False, 'message': 'Cannot modify your own admin account'})
            flash('Cannot modify your own admin account', 'error')
            return redirect(url_for('admin.users'))
            
        # Toggle admin status using is_admin field
        user.is_admin = not user.is_admin
        status_message = "granted to" if user.is_admin else "removed from"
            
        db.session.commit()
        
        if is_xhr_request(request):
            return jsonify({
                'success': True,
                'message': f"Admin status {status_message} {user.username}"
            })
            
        flash(f"Admin status {status_message} {user.username}", 'success')
        return redirect(url_for('admin.users'))
        
    except Exception as e:
        logger.error(f"Error toggling admin status: {str(e)}")
        db.session.rollback()
        flash('Error updating user', 'error')
        return redirect(url_for('admin.users'))

@admin_bp.route('/reset_user_password', methods=['POST'])
@login_required
@admin_required
def reset_user_password():
    try:
        import random
        import string
        from werkzeug.security import generate_password_hash
        
        user_id = request.form.get('user_id', type=int)
        if not user_id:
            if is_xhr_request(request):
                return jsonify({'success': False, 'message': 'Invalid user ID'})
            flash('Invalid user ID', 'error')
            return redirect(url_for('admin.users'))
            
        user = User.query.get(user_id)
        if not user:
            if is_xhr_request(request):
                return jsonify({'success': False, 'message': 'User not found'})
            flash('User not found', 'error')
            return redirect(url_for('admin.users'))
            
        # Generate a random password
        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        if is_xhr_request(request):
            return jsonify({
                'success': True, 
                'message': f"Password for {user.username} has been reset",
                'new_password': new_password
            })
            
        flash(f"Password for {user.username} has been reset to: {new_password}", 'success')
        return redirect(url_for('admin.users'))
        
    except Exception as e:
        logger.error(f"Error resetting password: {str(e)}")
        db.session.rollback()
        flash('Error resetting password', 'error')
        return redirect(url_for('admin.users'))

@admin_bp.route('/question/<int:question_id>')
@login_required
@admin_required
def question_detail(question_id):
    """Display detailed information about a specific question including all answers given to it."""
    try:
        question = Question.query.get_or_404(question_id)
        
        # Get all answers for this question
        question_answers = QuestionAnswer.query.filter_by(question_id=question_id)\
            .order_by(QuestionAnswer.created_at.desc()).all()
            
        # Group answers by game session
        answers_by_session = {}
        for answer in question_answers:
            if answer.game_session_id not in answers_by_session:
                answers_by_session[answer.game_session_id] = []
            answers_by_session[answer.game_session_id].append(answer)
            
        # Calculate statistics
        total_answers = len(question_answers)
        correct_answers = sum(1 for a in question_answers if a.is_correct)
        timer_expired_count = sum(1 for a in question_answers if a.timer_expired)
        
        incorrect_answers = total_answers - correct_answers - timer_expired_count
        stats = {
            'total_answers': total_answers,
            'correct_answers': correct_answers,
            'incorrect_answers': incorrect_answers,
            'timer_expired': timer_expired_count,
            'correct_percentage': round((correct_answers / total_answers * 100) if total_answers > 0 else 0, 1),
            'incorrect_percentage': round((incorrect_answers / total_answers * 100) if total_answers > 0 else 0, 1),
            'timer_expired_percentage': round((timer_expired_count / total_answers * 100) if total_answers > 0 else 0, 1),
            'avg_time': round(question.avg_time, 1) if question.avg_time else 0
        }
        
        # Get all users who have answered this question
        user_ids = set(a.user_id for a in question_answers)
        users = {user.id: user for user in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}
        
        # Get all game sessions for this question
        session_ids = set(a.game_session_id for a in question_answers)
        sessions = {session.id: session for session in GameSession.query.filter(GameSession.id.in_(session_ids)).all()} if session_ids else {}
        
        return render_template('admin/question_detail.html',
                           question=question,
                           question_answers=question_answers,
                           answers_by_session=answers_by_session,
                           stats=stats,
                           users=users,
                           sessions=sessions)
                           
    except Exception as e:
        logger.error(f"Error in question detail: {str(e)}")
        flash('Error loading question details', 'error')
        return redirect(url_for('admin.questions'))