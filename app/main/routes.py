"""Main application routes."""
from __future__ import annotations

from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required

# Create main blueprint
main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Landing page."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard."""
    return render_template('dashboard.html')


@main_bp.route('/about')
def about():
    """About page."""
    return render_template('about.html')


@main_bp.route('/contact')
def contact():
    """Contact page."""
    return render_template('contact.html')


@main_bp.route('/privacy')
def privacy():
    """Privacy policy page."""
    return render_template('privacy.html')


@main_bp.route('/terms')
def terms():
    """Terms of service page."""
    return render_template('terms.html')