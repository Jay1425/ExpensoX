"""Authentication routes."""
from __future__ import annotations

from typing import Any, Dict

from flask import current_app, request
from flask_login import login_required, login_user, logout_user

from app.__init__ import db
from app.models import Company, EmployeeProfile, User, UserRole
from app.services import currency_service
from app.utils.helpers import json_response

from . import auth_bp


@auth_bp.route("/signup", methods=["POST"])
def signup() -> Any:
    """Register a new user and optionally bootstrap the first company."""
    payload: Dict[str, Any] = request.get_json(silent=True) or {}

    required_fields = {"email", "password", "name"}
    if missing := required_fields - payload.keys():
        return json_response({"error": f"Missing required fields: {', '.join(sorted(missing))}"}, status=400)

    existing_user = User.query.filter_by(email=payload["email"].lower()).first()
    if existing_user:
        return json_response({"error": "Email already registered."}, status=409)

    is_bootstrap = Company.query.count() == 0

    company: Company | None = None
    user_role = payload.get("role", UserRole.ADMIN.value if is_bootstrap else UserRole.EMPLOYEE.value)

    try:
        role = UserRole[user_role.upper()]
    except KeyError:
        return json_response({"error": f"Unknown role '{user_role}'."}, status=400)

    if is_bootstrap:
        company_name = payload.get("company_name")
        country = payload.get("country")
        if not company_name or not country:
            return json_response(
                {"error": "First signup requires 'company_name' and 'country'."}, status=400
            )

        country_info = currency_service.get_default_currency_for_country(country)
        currency_code = country_info.get("currency_code") or current_app.config.get("DEFAULT_CURRENCY", "USD")

        company = Company(name=company_name, country=country, currency_code=currency_code)
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
            return json_response({"error": "Company not found."}, status=404)

    user = User(
        name=payload["name"],
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
                return json_response({"error": "Manager must belong to the same company."}, status=400)
        profile = EmployeeProfile(user_id=user.id, manager_id=manager_id)
        db.session.add(profile)

    db.session.commit()

    login_user(user)

    return json_response(
        {
            "message": "Signup successful.",
            "user": user.to_dict(),
            "company": company.to_dict() if company else None,
        },
        status=201,
    )


@auth_bp.route("/login", methods=["POST"])
def login() -> Any:
    """Authenticate a user using email/password."""
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    email = payload.get("email", "").lower()
    password = payload.get("password")

    if not email or not password:
        return json_response({"error": "Email and password are required."}, status=400)

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return json_response({"error": "Invalid credentials."}, status=401)

    if not user.is_active:
        return json_response({"error": "User account is inactive."}, status=403)

    remember = bool(payload.get("remember", False))
    login_user(user, remember=remember)

    return json_response({"message": "Login successful.", "user": user.to_dict()})


@auth_bp.route("/logout", methods=["GET"])
@login_required
def logout() -> Any:
    """Terminate the user session."""
    logout_user()
    return json_response({"message": "Logged out."})
