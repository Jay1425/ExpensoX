"""Application factory and extension initialization for ExpensoX."""
from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

from config import config_by_name

# Global extension instances -------------------------------------------------

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
mail = Mail()


def create_app(config_name: Optional[str] = None) -> Flask:
    """Flask application factory."""
    load_dotenv()

    app = Flask(__name__, instance_relative_config=True)

    config_name = config_name or os.getenv("FLASK_CONFIG", "development")
    config_class = config_by_name.get(config_name.lower())
    if config_class is None:
        raise ValueError(f"Unknown Flask configuration '{config_name}'")

    app.config.from_object(config_class)

    # Ensure instance folder exists for SQLite DBs or uploads
    os.makedirs(app.instance_path, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    csrf.init_app(app)
    mail.init_app(app)

    # Initialize email service
    from app.services.email_service import init_email_service
    init_email_service(mail)

    # Register blueprints
    from app.main import main_bp
    from app.auth import auth_bp
    from app.admin import admin_bp
    from app.employee import employee_bp
    from app.manager import manager_bp
    from app.otp import otp_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(manager_bp)
    app.register_blueprint(otp_bp)

    # User loader for Flask-Login
    from app.models import User
    # Import all models to ensure they are registered with SQLAlchemy
    from app.models import (
        Company, EmployeeProfile, Expense, ExpenseApproval, 
        ApprovalFlow, ApprovalRule, AuditLog, OTPVerification
    )

    @login_manager.user_loader
    def load_user(user_id: str) -> Optional[User]:
        return User.query.get(int(user_id))

    @app.shell_context_processor
    def shell_context():
        return {"db": db, "User": User}

    return app
