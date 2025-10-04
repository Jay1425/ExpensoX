"""Manager approval routes."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import request
from flask_login import current_user, login_required

from app.__init__ import db
from app.models import (
    ApprovalDecisionStatus,
    Expense,
    ExpenseApproval,
    ExpenseStatus,
    UserRole,
)
from app.services import approval_engine
from app.utils.helpers import json_response, role_required

from . import manager_bp


@manager_bp.route("/pending", methods=["GET"])
@login_required
@role_required(UserRole.MANAGER)
def pending_approvals() -> Any:
    """Return pending approvals assigned to the manager."""
    approvals = (
        ExpenseApproval.query.filter_by(
            approver_user_id=current_user.id, status=ApprovalDecisionStatus.PENDING
        )
        .join(Expense)
        .order_by(Expense.created_at.desc())
        .all()
    )
    return json_response({"approvals": [approval.to_dict() for approval in approvals]})


def _update_approval(expense_id: int, new_status: ApprovalDecisionStatus, comment: str | None) -> Any:
    approval = ExpenseApproval.query.filter_by(
        expense_id=expense_id,
        approver_user_id=current_user.id,
    ).order_by(ExpenseApproval.step_number.desc()).first()

    if approval is None or approval.status != ApprovalDecisionStatus.PENDING:
        return json_response({"error": "No pending approval found for this expense."}, status=404)

    expense = Expense.query.get(expense_id)
    if expense is None:
        return json_response({"error": "Expense not found."}, status=404)

    approval.status = new_status
    approval.comment = comment
    approval.acted_at = datetime.utcnow()

    if new_status == ApprovalDecisionStatus.APPROVED:
        expense.status = ExpenseStatus.APPROVED
        approval_engine.next_approver_logic(current_user, expense)
    elif new_status == ApprovalDecisionStatus.REJECTED:
        expense.status = ExpenseStatus.REJECTED

    db.session.commit()

    return json_response(
        {
            "message": f"Expense {new_status.value.lower()}.",
            "approval": approval.to_dict(),
            "expense": expense.to_dict(),
        }
    )


@manager_bp.route("/approve/<int:expense_id>", methods=["POST"])
@login_required
@role_required(UserRole.MANAGER)
def approve_expense(expense_id: int) -> Any:
    """Approve a pending expense."""
    comment = (request.get_json(silent=True) or {}).get("comment")
    return _update_approval(expense_id, ApprovalDecisionStatus.APPROVED, comment)


@manager_bp.route("/reject/<int:expense_id>", methods=["POST"])
@login_required
@role_required(UserRole.MANAGER)
def reject_expense(expense_id: int) -> Any:
    """Reject a pending expense."""
    comment = (request.get_json(silent=True) or {}).get("comment")
    return _update_approval(expense_id, ApprovalDecisionStatus.REJECTED, comment)
