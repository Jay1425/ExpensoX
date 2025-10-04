"""Employee-facing routes."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict

from flask import request, render_template, flash, redirect, url_for
from flask_login import current_user, login_required

from app.__init__ import db
from app.models import (
    ApprovalDecisionStatus,
    EmployeeProfile,
    Expense,
    ExpenseApproval,
    ExpenseStatus,
    UserRole,
)
from app.services import approval_engine, currency_service
from app.utils.helpers import json_response, role_required

from . import employee_bp


@employee_bp.route("/expenses", methods=["GET"])
@login_required
@role_required(UserRole.EMPLOYEE)
def list_expenses() -> Any:
    """List expenses submitted by the current employee."""
    expenses = (
        Expense.query.filter_by(submitter_user_id=current_user.id)
        .order_by(Expense.created_at.desc())
        .all()
    )
    
    if request.headers.get('Accept') == 'application/json':
        return json_response({"expenses": [expense.to_dict() for expense in expenses]})
    
    return render_template("employee/expenses.html", expenses=expenses)


@employee_bp.route("/expenses/submit", methods=["GET", "POST"])
@login_required
@role_required(UserRole.EMPLOYEE)
def submit_expense() -> Any:
    """Submit a new expense with minimal validation and placeholder approvals."""
    if request.method == "GET":
        return render_template("employee/submit_expense.html")
    
    # Handle form submission
    if request.content_type == "application/json":
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
    else:
        payload = request.form.to_dict()

    required_fields = {"amount", "currency", "category", "date_spent"}
    if missing := required_fields - payload.keys():
        error_msg = f"Missing fields: {', '.join(sorted(missing))}"
        if request.content_type == "application/json":
            return json_response({"error": error_msg}, status=400)
        else:
            flash(error_msg, "error")
            return redirect(url_for('employee.submit_expense'))

    try:
        amount_original = Decimal(str(payload["amount"]))
    except (InvalidOperation, TypeError):
        error_msg = "Invalid amount."
        if request.content_type == "application/json":
            return json_response({"error": error_msg}, status=400)
        else:
            flash(error_msg, "error")
            return redirect(url_for('employee.submit_expense'))

    try:
        spent_date = date.fromisoformat(payload["date_spent"])
    except (TypeError, ValueError):
        error_msg = "Invalid 'date_spent' format. Use YYYY-MM-DD."
        if request.content_type == "application/json":
            return json_response({"error": error_msg}, status=400)
        else:
            flash(error_msg, "error")
            return redirect(url_for('employee.submit_expense'))

    company = current_user.company
    target_currency = company.currency_code
    converted_amount = currency_service.convert_currency(
        amount_original, payload["currency"], target_currency
    )

    expense = Expense(
        company_id=company.id,
        submitter_user_id=current_user.id,
        amount_original=amount_original,
        currency_original=payload["currency"],
        amount_in_company_currency=converted_amount,
        category=payload["category"],
        description=payload.get("description"),
        date_spent=spent_date,
        status=ExpenseStatus.PENDING,
        receipt_path=payload.get("receipt_path"),
    )

    db.session.add(expense)
    db.session.flush()

    profile = EmployeeProfile.query.filter_by(user_id=current_user.id).first()
    approver_id = approval_engine.next_approver_logic(current_user, expense)
    if approver_id is None and profile and profile.manager_id:
        approver_id = profile.manager_id

    approval = ExpenseApproval(
        expense_id=expense.id,
        approver_user_id=approver_id,
        step_number=1,
        status=ApprovalDecisionStatus.PENDING,
    )
    db.session.add(approval)

    db.session.commit()

    approval_engine.evaluate_rules(expense)

    if request.content_type == "application/json":
        return json_response(
            {
                "message": "Expense submitted.",
                "expense": expense.to_dict(),
                "approval": approval.to_dict(),
            },
            status=201,
        )
    else:
        flash("Expense submitted successfully!", "success")
        return redirect(url_for('employee.list_expenses'))


@employee_bp.route("/dashboard", methods=["GET"])
@login_required
@role_required(UserRole.EMPLOYEE)
def dashboard() -> Any:
    """Employee dashboard with expense overview."""
    # Get recent expenses
    recent_expenses = (
        Expense.query.filter_by(submitter_user_id=current_user.id)
        .order_by(Expense.created_at.desc())
        .limit(5)
        .all()
    )
    
    # Get expense statistics
    total_expenses = Expense.query.filter_by(submitter_user_id=current_user.id).count()
    pending_expenses = Expense.query.filter_by(
        submitter_user_id=current_user.id,
        status=ExpenseStatus.PENDING
    ).count()
    approved_expenses = Expense.query.filter_by(
        submitter_user_id=current_user.id,
        status=ExpenseStatus.APPROVED
    ).count()
    
    stats = {
        "total_expenses": total_expenses,
        "pending_expenses": pending_expenses,
        "approved_expenses": approved_expenses,
        "recent_expenses": recent_expenses
    }
    
    if request.headers.get('Accept') == 'application/json':
        return json_response(stats)
    
    return render_template("employee/dashboard.html", stats=stats)


@employee_bp.route("/expenses/<int:expense_id>", methods=["GET"])
@login_required
@role_required(UserRole.EMPLOYEE)
def expense_detail(expense_id: int) -> Any:
    """View detailed information about a specific expense."""
    expense = Expense.query.filter_by(
        id=expense_id,
        submitter_user_id=current_user.id
    ).first()
    
    if not expense:
        if request.headers.get('Accept') == 'application/json':
            return json_response({"error": "Expense not found."}, status=404)
        flash("Expense not found.", "error")
        return redirect(url_for('employee.list_expenses'))
    
    # Get approval history
    approvals = ExpenseApproval.query.filter_by(expense_id=expense_id).all()
    
    if request.headers.get('Accept') == 'application/json':
        return json_response({
            "expense": expense.to_dict(),
            "approvals": [approval.to_dict() for approval in approvals]
        })
    
    return render_template("employee/expense_detail.html", expense=expense, approvals=approvals)


@employee_bp.route("/profile", methods=["GET", "POST"])
@login_required
@role_required(UserRole.EMPLOYEE)
def profile() -> Any:
    """View and edit employee profile."""
    if request.method == "GET":
        profile = EmployeeProfile.query.filter_by(user_id=current_user.id).first()
        return render_template("employee/profile.html", profile=profile)
    
    # Handle profile updates
    if request.content_type == "application/json":
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
    else:
        payload = request.form.to_dict()
    
    # Update user basic info
    if 'first_name' in payload:
        current_user.first_name = payload['first_name']
    if 'last_name' in payload:
        current_user.last_name = payload['last_name']
    
    # Update employee profile
    profile = EmployeeProfile.query.filter_by(user_id=current_user.id).first()
    if profile:
        if 'department' in payload:
            profile.department = payload['department']
        if 'phone_number' in payload:
            profile.phone_number = payload['phone_number']
    
    db.session.commit()
    
    if request.content_type == "application/json":
        return json_response({"message": "Profile updated successfully."})
    else:
        flash("Profile updated successfully!", "success")
        return redirect(url_for('employee.profile'))
