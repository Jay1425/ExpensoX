"""General helper utilities."""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import jsonify
from flask_login import current_user

from app.models import UserRole

JsonView = Callable[..., Any]


def json_response(payload: Any, status: int = 200):
    """Return a JSON response with status code."""
    return jsonify(payload), status


def role_required(*roles: UserRole):
    """Restrict a route to one or more roles."""
    def decorator(view_func: JsonView) -> JsonView:
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return json_response({"error": "Authentication required."}, status=401)
            if current_user.role not in roles:
                return json_response({"error": "Insufficient permissions."}, status=403)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator
