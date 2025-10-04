"""Employee-facing routes."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict

from flask import request
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
    return json_response({"expenses": [expense.to_dict() for expense in expenses]})


@employee_bp.route("/expenses", methods=["POST"])
@login_required
@role_required(UserRole.EMPLOYEE)
def submit_expense() -> Any:
    """Submit a new expense with minimal validation and placeholder approvals."""
    payload: Dict[str, Any] = request.get_json(silent=True) or {}

    required_fields = {"amount", "currency", "category", "date_spent"}
    if missing := required_fields - payload.keys():
        return json_response({"error": f"Missing fields: {', '.join(sorted(missing))}"}, status=400)

    try:
        amount_original = Decimal(str(payload["amount"]))
    except (InvalidOperation, TypeError):
        return json_response({"error": "Invalid amount."}, status=400)

    try:
        spent_date = date.fromisoformat(payload["date_spent"])
    except (TypeError, ValueError):
        return json_response({"error": "Invalid 'date_spent' format. Use YYYY-MM-DD."}, status=400)

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

    return json_response(
        {
            "message": "Expense submitted.",
            "expense": expense.to_dict(),
            "approval": approval.to_dict(),
        },
        status=201,
    )
