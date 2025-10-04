from flask import Flask
from flask_wtf import CSRFProtect
from dotenv import load_dotenv

from auth import auth_bp
from config import Config
from database.models import bcrypt, db

load_dotenv()

csrf = CSRFProtect()


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_class)

    db.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(auth_bp)

    @app.shell_context_processor
    def make_shell_context():
        return {"db": db}

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)