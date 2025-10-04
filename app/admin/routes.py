"""Administrative routes."""
from __future__ import annotations

from typing import Any, Dict

from flask import request
from flask_login import current_user, login_required

from app.__init__ import db
from app.models import ApprovalFlow, ApprovalRule, ApprovalRuleType, EmployeeProfile, User, UserRole
from app.services import approval_engine
from app.utils.helpers import json_response, role_required

from . import admin_bp


@admin_bp.route("/users", methods=["GET"])
@login_required
@role_required(UserRole.ADMIN)
def list_users() -> Any:
    """Return all users in the admin's company."""
    users = User.query.filter_by(company_id=current_user.company_id).all()
    return json_response({"users": [user.to_dict() for user in users]})


@admin_bp.route("/users", methods=["POST"])
@login_required
@role_required(UserRole.ADMIN)
def create_user() -> Any:
    """Create a new employee or manager."""
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    required_fields = {"name", "email", "password", "role"}
    if missing := required_fields - payload.keys():
        return json_response({"error": f"Missing fields: {', '.join(sorted(missing))}"}, status=400)

    email = payload["email"].lower()
    if User.query.filter_by(email=email).first():
        return json_response({"error": "Email already exists."}, status=409)

    try:
        role = UserRole[payload["role"].upper()]
    except KeyError:
        return json_response({"error": "Unsupported role."}, status=400)

    manager_id = payload.get("manager_id") if role == UserRole.EMPLOYEE else None
    if manager_id:
        manager = User.query.get(manager_id)
        if manager is None or manager.company_id != current_user.company_id:
            return json_response({"error": "Invalid manager selected."}, status=400)

    new_user = User(
        name=payload["name"],
        email=email,
        role=role,
        company_id=current_user.company_id,
        is_active=payload.get("is_active", True),
    )
    new_user.set_password(payload["password"])

    db.session.add(new_user)
    db.session.flush()

    if role in {UserRole.MANAGER, UserRole.EMPLOYEE}:
        profile = EmployeeProfile(user_id=new_user.id, manager_id=manager_id)
        db.session.add(profile)

    db.session.commit()

    return json_response({"message": "User created.", "user": new_user.to_dict()}, status=201)


@admin_bp.route("/approval-flow", methods=["POST"])
@login_required
@role_required(UserRole.ADMIN)
def create_or_update_flow() -> Any:
    """Create a new approval flow or update an existing one."""
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    name = payload.get("name")
    steps = payload.get("steps", [])
    is_default = bool(payload.get("is_default", False))

    if not name or not isinstance(steps, (list, tuple)):
        return json_response({"error": "'name' and list of 'steps' are required."}, status=400)

    flow = ApprovalFlow.query.filter_by(company_id=current_user.company_id, name=name).first()
    if flow is None:
        flow = ApprovalFlow(company_id=current_user.company_id, name=name, steps=steps)
        db.session.add(flow)
    else:
        flow.steps = steps
    flow.is_default = is_default

    approval_engine.create_approval_flow(flow, steps=steps)

    db.session.commit()

    return json_response({"message": "Approval flow saved.", "flow": flow.to_dict()})


@admin_bp.route("/approval-rule", methods=["POST"])
@login_required
@role_required(UserRole.ADMIN)
def create_or_update_rule() -> Any:
    """Create or update approval rules."""
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    rule_type = payload.get("rule_type")

    try:
        rule_enum = ApprovalRuleType[rule_type.upper()]
    except (AttributeError, KeyError):
        return json_response({"error": "Invalid rule_type."}, status=400)

    rule = ApprovalRule(
        company_id=current_user.company_id,
        rule_type=rule_enum,
        percentage_threshold=payload.get("percentage_threshold"),
        specific_approver_id=payload.get("specific_approver_id"),
    )

    db.session.add(rule)
    db.session.commit()

    evaluation_preview = approval_engine.evaluate_rules(rule)

    return json_response(
        {
            "message": "Approval rule created.",
            "rule": rule.to_dict(),
            "evaluation_preview": evaluation_preview,
        },
        status=201,
    )
