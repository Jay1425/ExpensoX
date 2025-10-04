"""Authentication routes."""
from __future__ import annotations

from typing import Any, Dict

from flask import current_app, request, render_template, flash, redirect, url_for, session
from flask_login import login_required, login_user, logout_user, current_user

from app.__init__ import db
from app.models import Company, EmployeeProfile, User, UserRole
from app.services import currency_service
from app.services.otp_service import otp_service
from app.utils.helpers import json_response

from . import auth_bp


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup() -> Any:
    """Register a new user and optionally bootstrap the first company."""
    if request.method == "GET":
        return render_template("auth/signup.html")
    
    # Handle form submission
    if request.content_type == "application/json":
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
    else:
        payload = request.form.to_dict()

    required_fields = {"email", "password", "first_name", "last_name"}
    if missing := required_fields - payload.keys():
        if request.content_type == "application/json":
            return json_response({"error": f"Missing required fields: {', '.join(sorted(missing))}"}, status=400)
        flash(f"Missing required fields: {', '.join(sorted(missing))}", "error")
        return render_template("auth/signup.html")

    existing_user = User.query.filter_by(email=payload["email"].lower()).first()
    if existing_user:
        if request.content_type == "application/json":
            return json_response({"error": "Email already registered."}, status=409)
        flash("Email already registered.", "error")
        return render_template("auth/signup.html")

    is_bootstrap = Company.query.count() == 0

    company: Company | None = None
    user_role = payload.get("role", UserRole.ADMIN.value if is_bootstrap else UserRole.EMPLOYEE.value)

    try:
        role = UserRole[user_role.upper()]
    except KeyError:
        if request.content_type == "application/json":
            return json_response({"error": f"Unknown role '{user_role}'."}, status=400)
        flash(f"Unknown role '{user_role}'.", "error")
        return render_template("auth/signup.html")

    if is_bootstrap:
        company_name = payload.get("company_name")
        if not company_name:
            if request.content_type == "application/json":
                return json_response({"error": "Company name is required for first signup."}, status=400)
            flash("Company name is required for first signup.", "error")
            return render_template("auth/signup.html")

        currency_code = current_app.config.get("DEFAULT_CURRENCY", "USD")
        company = Company(name=company_name, currency_code=currency_code)
        db.session.add(company)
        role = UserRole.ADMIN
    else:
        company_id = payload.get("company_id")
        company_name = payload.get("company_name")
        if company_id:
            company = Company.query.get(company_id)
        elif company_name:
            company = Company.query.filter_by(name=company_name).first()

        if company is None:
            if request.content_type == "application/json":
                return json_response({"error": "Company not found."}, status=404)
            flash("Company not found.", "error")
            return render_template("auth/signup.html")

    user = User(
        first_name=payload["first_name"],
        last_name=payload["last_name"],
        email=payload["email"].lower(),
        role=role,
        company=company,
    )
    user.set_password(payload["password"])

    db.session.add(user)
    db.session.flush()

    if role in {UserRole.EMPLOYEE, UserRole.MANAGER}:
        manager_id = payload.get("manager_id")
        if manager_id:
            manager = User.query.get(manager_id)
            if manager is None or manager.company_id != user.company_id:
                db.session.rollback()
                if request.content_type == "application/json":
                    return json_response({"error": "Manager must belong to the same company."}, status=400)
                flash("Manager must belong to the same company.", "error")
                return render_template("auth/signup.html")
        profile = EmployeeProfile(user_id=user.id, manager_id=manager_id)
        db.session.add(profile)

    db.session.commit()

    # Send OTP for email verification
    session['pending_user_id'] = user.id
    success, message = otp_service.generate_and_send_otp(
        user_id=user.id,
        otp_type='signup',
        email=user.email,
        user_name=user.first_name
    )
    
    if success:
        flash("Registration successful! Please check your email for a verification code.", "success")
        return redirect(url_for('otp.verify_page', otp_type='signup'))
    else:
        flash(f"Registration successful, but failed to send verification email: {message}", "warning")
        login_user(user)
        return redirect(url_for('main.dashboard'))


@auth_bp.route("/login", methods=["GET", "POST"])
def login() -> Any:
    """Authenticate a user using email/password."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == "GET":
        return render_template("auth/login.html")
    
    # Handle form submission
    if request.content_type == "application/json":
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
    else:
        payload = request.form.to_dict()
        
    email = payload.get("email", "").lower()
    password = payload.get("password")

    if not email or not password:
        if request.content_type == "application/json":
            return json_response({"error": "Email and password are required."}, status=400)
        flash("Email and password are required.", "error")
        return render_template("auth/login.html")

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        if request.content_type == "application/json":
            return json_response({"error": "Invalid credentials."}, status=401)
        flash("Invalid email or password.", "error")
        return render_template("auth/login.html")

    if not user.is_active:
        if request.content_type == "application/json":
            return json_response({"error": "User account is inactive."}, status=403)
        flash("Your account has been deactivated. Please contact support.", "error")
        return render_template("auth/login.html")

    # Check if email is verified
    if not user.is_email_verified:
        session['pending_user_id'] = user.id
        success, message = otp_service.generate_and_send_otp(
            user_id=user.id,
            otp_type='signup',
            email=user.email,
            user_name=user.first_name
        )
        flash("Please verify your email address first.", "warning")
        return redirect(url_for('otp.verify_page', otp_type='signup'))

    remember = bool(payload.get("remember", False))
    login_user(user, remember=remember)

    if request.content_type == "application/json":
        return json_response({"message": "Login successful.", "user": user.to_dict()})
    
    flash("Welcome back!", "success")
    next_page = request.args.get('next')
    return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))


@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout() -> Any:
    """Terminate the user session."""
    logout_user()
    session.clear()
    
    if request.content_type == "application/json":
        return json_response({"message": "Logged out."})
    
    flash("You have been logged out.", "success")
    return redirect(url_for('main.index'))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile() -> Any:
    """User profile management."""
    if request.method == "GET":
        return render_template("auth/profile.html")
    
    # Handle profile update
    if request.content_type == "application/json":
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
    else:
        payload = request.form.to_dict()
    
    user = current_user
    
    # Update basic info
    if 'first_name' in payload:
        user.first_name = payload['first_name']
    if 'last_name' in payload:
        user.last_name = payload['last_name']
    if 'email' in payload and payload['email'] != user.email:
        # Check if email is already taken
        existing = User.query.filter_by(email=payload['email']).first()
        if existing and existing.id != user.id:
            flash("Email is already in use.", "error")
            return render_template("auth/profile.html")
        user.email = payload['email']
        user.is_email_verified = False  # Need to re-verify
    
    # Handle password change
    current_password = payload.get('current_password')
    new_password = payload.get('new_password')
    confirm_password = payload.get('confirm_new_password')
    
    if current_password and new_password:
        if not user.check_password(current_password):
            flash("Current password is incorrect.", "error")
            return render_template("auth/profile.html")
        
        if new_password != confirm_password:
            flash("New passwords do not match.", "error")
            return render_template("auth/profile.html")
        
        user.set_password(new_password)
        flash("Password updated successfully.", "success")
    
    db.session.commit()
    
    if request.content_type == "application/json":
        return json_response({"message": "Profile updated successfully.", "user": user.to_dict()})
    
    flash("Profile updated successfully.", "success")
    return render_template("auth/profile.html")


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password() -> Any:
    """Handle forgot password requests."""
    if request.method == "GET":
        return render_template("auth/forgot_password.html")
    
    # Handle form submission
    if request.content_type == "application/json":
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
    else:
        payload = request.form.to_dict()
    
    email = payload.get("email", "").lower()
    
    if not email:
        flash("Email address is required.", "error")
        return render_template("auth/forgot_password.html")
    
    user = User.query.filter_by(email=email).first()
    
    if user:
        # Send OTP for password reset
        session['pending_user_id'] = user.id
        success, message = otp_service.generate_and_send_otp(
            user_id=user.id,
            otp_type='password_reset',
            email=user.email,
            user_name=user.first_name
        )
        
        if success:
            flash("Password reset code sent to your email.", "success")
            return redirect(url_for('otp.verify_page', otp_type='password_reset'))
        else:
            flash(f"Failed to send password reset code: {message}", "error")
    else:
        # Don't reveal if email exists or not for security
        flash("If an account with that email exists, you will receive a password reset code.", "info")
    
    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password() -> Any:
    """Reset password after OTP verification."""
    if not session.get('password_reset_verified'):
        flash("Please complete email verification first.", "error")
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == "GET":
        return render_template("otp/reset_password.html")
    
    # Handle password reset
    payload = request.form.to_dict()
    new_password = payload.get('new_password')
    confirm_password = payload.get('confirm_password')
    
    if not new_password or not confirm_password:
        flash("Both password fields are required.", "error")
        return render_template("otp/reset_password.html")
    
    if new_password != confirm_password:
        flash("Passwords do not match.", "error")
        return render_template("otp/reset_password.html")
    
    user_id = session.get('password_reset_user_id')
    user = User.query.get(user_id)
    
    if not user:
        flash("Invalid reset session.", "error")
        return redirect(url_for('auth.forgot_password'))
    
    user.set_password(new_password)
    db.session.commit()
    
    # Clear reset session
    session.pop('password_reset_verified', None)
    session.pop('password_reset_user_id', None)
    
    flash("Password reset successfully. Please log in with your new password.", "success")
    return redirect(url_for('auth.login'))


@auth_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings() -> Any:
    """User settings page."""
    if request.method == "GET":
        return render_template("auth/settings.html")
    
    # Handle settings update
    payload = request.form.to_dict()
    user = current_user
    
    # Update two-factor authentication setting
    if 'two_factor_enabled' in payload:
        user.two_factor_enabled = payload['two_factor_enabled'] == 'on'
        db.session.commit()
        
        if user.two_factor_enabled:
            flash("Two-factor authentication enabled.", "success")
        else:
            flash("Two-factor authentication disabled.", "info")
    
    return render_template("auth/settings.html")
