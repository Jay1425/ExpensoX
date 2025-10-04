"""Manager blueprint."""
from flask import Blueprint

manager_bp = Blueprint("manager", __name__, url_prefix="/manager")

from . import routes  # noqa: E402,F401
