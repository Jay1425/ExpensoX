"""Expense model definitions."""
from __future__ import annotations

import enum

from app.__init__ import db


class ExpenseStatus(enum.Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PAID = "PAID"


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    submitter_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount_original = db.Column(db.Numeric(12, 2), nullable=False)
    currency_original = db.Column(db.String(10), nullable=False)
    amount_in_company_currency = db.Column(db.Numeric(12, 2), nullable=True)
    category = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date_spent = db.Column(db.Date, nullable=False)
    status = db.Column(db.Enum(ExpenseStatus, name="expense_status"), nullable=False, default=ExpenseStatus.PENDING)
    receipt_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    company = db.relationship("Company", back_populates="expenses", lazy="joined")
    submitter = db.relationship("User", back_populates="submitted_expenses", lazy="joined")
    approvals = db.relationship(
        "ExpenseApproval",
        back_populates="expense",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "submitter_user_id": self.submitter_user_id,
            "amount_original": float(self.amount_original) if self.amount_original is not None else None,
            "currency_original": self.currency_original,
            "amount_in_company_currency": float(self.amount_in_company_currency)
            if self.amount_in_company_currency is not None
            else None,
            "category": self.category,
            "description": self.description,
            "date_spent": self.date_spent.isoformat() if self.date_spent else None,
            "status": self.status.value if self.status else None,
            "receipt_path": self.receipt_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Expense id={self.id} status={self.status.value if self.status else None}>"
