from flask import Blueprint

expenses_bp = Blueprint("expenses", __name__, template_folder="../templates")

from . import routes  # noqa: E402,F401
