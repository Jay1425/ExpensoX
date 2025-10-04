"""Company model."""
from __future__ import annotations

from app.__init__ import db


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    country = db.Column(db.String(120), nullable=False)
    currency_code = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    users = db.relationship(
        "User",
        back_populates="company",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    expenses = db.relationship(
        "Expense",
        back_populates="company",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    approval_flows = db.relationship(
        "ApprovalFlow",
        back_populates="company",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    approval_rules = db.relationship(
        "ApprovalRule",
        back_populates="company",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "country": self.country,
            "currency_code": self.currency_code,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Company {self.name}>"
