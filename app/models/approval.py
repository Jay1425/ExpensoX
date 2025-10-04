"""Approval-related models."""
from __future__ import annotations

import enum

from app.__init__ import db


class ApprovalDecisionStatus(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"


class ApprovalRuleType(enum.Enum):
    PERCENTAGE = "PERCENTAGE"
    SPECIFIC = "SPECIFIC"
    HYBRID = "HYBRID"


class ExpenseApproval(db.Model):
    __tablename__ = "expense_approvals"

    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(db.Integer, db.ForeignKey("expenses.id"), nullable=False, index=True)
    approver_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    step_number = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(
        db.Enum(ApprovalDecisionStatus, name="approval_decision_status"),
        nullable=False,
        default=ApprovalDecisionStatus.PENDING,
    )
    comment = db.Column(db.Text, nullable=True)
    acted_at = db.Column(db.DateTime, nullable=True)

    expense = db.relationship("Expense", back_populates="approvals", lazy="joined")
    approver = db.relationship("User", back_populates="approvals", lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "expense_id": self.expense_id,
            "approver_user_id": self.approver_user_id,
            "step_number": self.step_number,
            "status": self.status.value if self.status else None,
            "comment": self.comment,
            "acted_at": self.acted_at.isoformat() if self.acted_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"<ExpenseApproval expense_id={self.expense_id} "
            f"status={self.status.value if self.status else None}>"
        )


class ApprovalFlow(db.Model):
    __tablename__ = "approval_flows"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    steps = db.Column(db.JSON, nullable=False)
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    company = db.relationship("Company", back_populates="approval_flows", lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "name": self.name,
            "steps": self.steps,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<ApprovalFlow {self.name}>"


class ApprovalRule(db.Model):
    __tablename__ = "approval_rules"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    rule_type = db.Column(db.Enum(ApprovalRuleType, name="approval_rule_type"), nullable=False)
    percentage_threshold = db.Column(db.Numeric(5, 2), nullable=True)
    specific_approver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    company = db.relationship("Company", back_populates="approval_rules", lazy="joined")
    specific_approver = db.relationship("User", lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "rule_type": self.rule_type.value if self.rule_type else None,
            "percentage_threshold": float(self.percentage_threshold)
            if self.percentage_threshold is not None
            else None,
            "specific_approver_id": self.specific_approver_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<ApprovalRule id={self.id} type={self.rule_type.value if self.rule_type else None}>"
