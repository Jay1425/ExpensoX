from flask import Flask
from flask_wtf import CSRFProtect
from flask_migrate import Migrate
from dotenv import load_dotenv

from auth import auth_bp
from expenses import expenses_bp
from auth.admin_routes import auth_admin_bp
from dashboard import dashboard_bp
from blueprints.admin.routes import admin_bp
from blueprints.employee.routes import employee_bp
from manager import manager_bp
from config import Config
from database.models import bcrypt, db

load_dotenv()

csrf = CSRFProtect()
migrate = Migrate()


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_class)

    db.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        db.create_all()

    app.register_blueprint(auth_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(auth_admin_bp, url_prefix='/auth-admin')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(manager_bp)

    @app.shell_context_processor
    def make_shell_context():
        return {"db": db}

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)