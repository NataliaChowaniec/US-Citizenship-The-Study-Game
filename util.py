from functools import wraps
from flask import abort, redirect, url_for, flash
from flask_login import current_user
import logging

logger = logging.getLogger(__name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('You need to login first', 'danger')
            return redirect(url_for('login'))
            
        # Debugging line - check this in your server logs
        logger.info(f"Admin check - User: {current_user.email}, is_admin: {current_user.is_admin}")
        
        if not current_user.is_admin:
            flash('Admin access required', 'danger')
            return redirect(url_for('admin.dashboard'))
            
        return f(*args, **kwargs)
    return decorated_function