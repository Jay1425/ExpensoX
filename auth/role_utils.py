from functools import wraps
from flask import session, redirect, url_for, flash
from database.models import User

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                flash("Please log in to access this page.", "warning")
                return redirect(url_for("auth.login"))
            user = User.query.get(user_id)
            if not user or user.role.value != role:
                flash(f"Access denied: {role} role required.", "danger")
                return redirect(url_for("auth.dashboard"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
