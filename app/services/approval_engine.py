"""Approval engine stubs for multi-level workflow logic."""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from app.models import ApprovalFlow, ApprovalRule, Expense, User


def create_approval_flow(flow: ApprovalFlow, steps: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Persist approval flow metadata and return a summary."""
    flow.steps = list(steps)
    return {"flow_id": flow.id, "steps": flow.steps}


def evaluate_rules(entity: ApprovalRule | Expense) -> Dict[str, Any]:
    """Evaluate approval rules against the given entity (stub)."""
    # TODO: Implement complex rule evaluation logic in later phases.
    return {"status": "evaluation_pending", "entity": getattr(entity, "id", None)}


def next_approver_logic(user: User, expense: Expense) -> Optional[int]:
    """Determine the next approver user ID for the expense."""
    # TODO: Add sophisticated routing logic based on flow, rules, and org chart.
    return getattr(user.employee_profile, "manager_id", None) if user.employee_profile else None
