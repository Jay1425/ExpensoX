"""Administrative routes."""
from __future__ import annotations

from typing import Any, Dict

from flask import request, render_template, flash, redirect, url_for
from flask_login import current_user, login_required

from app.__init__ import db
from app.models import ApprovalFlow, ApprovalRule, ApprovalRuleType, EmployeeProfile, User, UserRole
from app.services import approval_engine
from app.utils.helpers import json_response, role_required

from . import admin_bp


@admin_bp.route("/users", methods=["GET"])
@login_required
@role_required(UserRole.ADMIN)
def users() -> Any:
    """Display all users in the admin's company."""
    if request.headers.get('Accept') == 'application/json':
        users = User.query.filter_by(company_id=current_user.company_id).all()
        return json_response({"users": [user.to_dict() for user in users]})
    
    users = User.query.filter_by(company_id=current_user.company_id).all()
    return render_template("admin/users.html", users=users)


@admin_bp.route("/users/create", methods=["GET", "POST"])
@login_required
@role_required(UserRole.ADMIN)
def create_user() -> Any:
    """Create a new employee or manager."""
    if request.method == "GET":
        managers = User.query.filter_by(
            company_id=current_user.company_id,
            role=UserRole.MANAGER
        ).all()
        return render_template("admin/create_user.html", managers=managers)
    
    if request.content_type == "application/json":
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
    else:
        payload = request.form.to_dict()
    required_fields = {"name", "email", "password", "role"}
    if missing := required_fields - payload.keys():
        error_msg = f"Missing fields: {', '.join(sorted(missing))}"
        if request.content_type == "application/json":
            return json_response({"error": error_msg}, status=400)
        else:
            flash(error_msg, "error")
            return redirect(url_for('admin.create_user'))

    email = payload["email"].lower()
    if User.query.filter_by(email=email).first():
        error_msg = "Email already exists."
        if request.content_type == "application/json":
            return json_response({"error": error_msg}, status=409)
        else:
            flash(error_msg, "error")
            return redirect(url_for('admin.create_user'))

    try:
        role = UserRole[payload["role"].upper()]
    except KeyError:
        error_msg = "Unsupported role."
        if request.content_type == "application/json":
            return json_response({"error": error_msg}, status=400)
        else:
            flash(error_msg, "error")
            return redirect(url_for('admin.create_user'))

    manager_id = payload.get("manager_id") if role == UserRole.EMPLOYEE else None
    if manager_id:
        manager = User.query.get(manager_id)
        if manager is None or manager.company_id != current_user.company_id:
            error_msg = "Invalid manager selected."
            if request.content_type == "application/json":
                return json_response({"error": error_msg}, status=400)
            else:
                flash(error_msg, "error")
                return redirect(url_for('admin.create_user'))

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

    if request.content_type == "application/json":
        return json_response({"message": "User created.", "user": new_user.to_dict()}, status=201)
    else:
        flash("User created successfully!", "success")
        return redirect(url_for('admin.users'))


@admin_bp.route("/approval-flows", methods=["GET"])
@login_required
@role_required(UserRole.ADMIN)
def approval_flows() -> Any:
    """Display approval flows."""
    flows = ApprovalFlow.query.filter_by(company_id=current_user.company_id).all()
    if request.headers.get('Accept') == 'application/json':
        return json_response({"flows": [flow.to_dict() for flow in flows]})
    return render_template("admin/approval_flows.html", flows=flows)


@admin_bp.route("/approval-flows/create", methods=["GET", "POST"])
@login_required
@role_required(UserRole.ADMIN)
def create_or_update_flow() -> Any:
    """Create a new approval flow or update an existing one."""
    if request.method == "GET":
        return render_template("admin/create_approval_flow.html")
    
    if request.content_type == "application/json":
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
    else:
        payload = request.form.to_dict()
        payload["steps"] = request.form.getlist("steps")
        payload["is_default"] = "is_default" in request.form
    
    name = payload.get("name")
    steps = payload.get("steps", [])
    is_default = bool(payload.get("is_default", False))

    if not name or not isinstance(steps, (list, tuple)):
        error_msg = "'name' and list of 'steps' are required."
        if request.content_type == "application/json":
            return json_response({"error": error_msg}, status=400)
        else:
            flash(error_msg, "error")
            return redirect(url_for('admin.create_or_update_flow'))

    flow = ApprovalFlow.query.filter_by(company_id=current_user.company_id, name=name).first()
    if flow is None:
        flow = ApprovalFlow(company_id=current_user.company_id, name=name, steps=steps)
        db.session.add(flow)
    else:
        flow.steps = steps
    flow.is_default = is_default

    approval_engine.create_approval_flow(flow, steps=steps)
    db.session.commit()

    if request.content_type == "application/json":
        return json_response({"message": "Approval flow saved.", "flow": flow.to_dict()})
    else:
        flash("Approval flow saved successfully!", "success")
        return redirect(url_for('admin.approval_flows'))


@admin_bp.route("/approval-rules", methods=["GET"])
@login_required
@role_required(UserRole.ADMIN)
def approval_rules() -> Any:
    """Display approval rules."""
    rules = ApprovalRule.query.filter_by(company_id=current_user.company_id).all()
    if request.headers.get('Accept') == 'application/json':
        return json_response({"rules": [rule.to_dict() for rule in rules]})
    return render_template("admin/approval_rules.html", rules=rules)


@admin_bp.route("/approval-rules/create", methods=["GET", "POST"])
@login_required
@role_required(UserRole.ADMIN)
def create_or_update_rule() -> Any:
    """Create or update approval rules."""
    if request.method == "GET":
        approvers = User.query.filter_by(
            company_id=current_user.company_id,
            role=UserRole.MANAGER
        ).all()
        return render_template("admin/create_approval_rule.html", approvers=approvers)
    
    if request.content_type == "application/json":
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
    else:
        payload = request.form.to_dict()
    
    rule_type = payload.get("rule_type")

    try:
        rule_enum = ApprovalRuleType[rule_type.upper()]
    except (AttributeError, KeyError):
        error_msg = "Invalid rule_type."
        if request.content_type == "application/json":
            return json_response({"error": error_msg}, status=400)
        else:
            flash(error_msg, "error")
            return redirect(url_for('admin.create_or_update_rule'))

    rule = ApprovalRule(
        company_id=current_user.company_id,
        rule_type=rule_enum,
        percentage_threshold=payload.get("percentage_threshold"),
        specific_approver_id=payload.get("specific_approver_id"),
    )

    db.session.add(rule)
    db.session.commit()

    evaluation_preview = approval_engine.evaluate_rules(rule)

    if request.content_type == "application/json":
        return json_response(
            {
                "message": "Approval rule created.",
                "rule": rule.to_dict(),
                "evaluation_preview": evaluation_preview,
            },
            status=201,
        )
    else:
        flash("Approval rule created successfully!", "success")
        return redirect(url_for('admin.approval_rules'))


@admin_bp.route("/dashboard", methods=["GET"])
@login_required
@role_required(UserRole.ADMIN)
def dashboard() -> Any:
    """Admin dashboard with system overview."""
    user_count = User.query.filter_by(company_id=current_user.company_id).count()
    flow_count = ApprovalFlow.query.filter_by(company_id=current_user.company_id).count()
    rule_count = ApprovalRule.query.filter_by(company_id=current_user.company_id).count()
    
    stats = {
        "user_count": user_count,
        "flow_count": flow_count,
        "rule_count": rule_count
    }
    
    if request.headers.get('Accept') == 'application/json':
        return json_response(stats)
    
    return render_template("admin/dashboard.html", stats=stats)
