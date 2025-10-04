"""User-related models."""
from __future__ import annotations

import enum
from typing import Optional

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.__init__ import db


class UserRole(enum.Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    EMPLOYEE = "EMPLOYEE"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole, name="user_role"), nullable=False, default=UserRole.EMPLOYEE)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_email_verified = db.Column(db.Boolean, default=False, nullable=False)
    two_factor_enabled = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    company = db.relationship("Company", back_populates="users", lazy="joined")
    employee_profile = db.relationship(
        "EmployeeProfile",
        back_populates="user",
        uselist=False,
        lazy="joined",
        cascade="all, delete-orphan",
    )
    managed_employees = db.relationship(
        "EmployeeProfile",
        foreign_keys="EmployeeProfile.manager_id",
        back_populates="manager",
        lazy="selectin",
    )
    submitted_expenses = db.relationship(
        "Expense",
        foreign_keys="Expense.submitter_user_id",
        back_populates="submitter",
        lazy="selectin",
    )
    approvals = db.relationship(
        "ExpenseApproval",
        foreign_keys="ExpenseApproval.approver_user_id",
        back_populates="approver",
        lazy="selectin",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_id(self) -> str:
        return str(self.id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": f"{self.first_name} {self.last_name}",
            "email": self.email,
            "role": self.role.value,
            "company_id": self.company_id,
            "is_active": self.is_active,
            "is_email_verified": self.is_email_verified,
            "two_factor_enabled": self.two_factor_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class EmployeeProfile(db.Model):
    __tablename__ = "employee_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    manager_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="employee_profile",
        lazy="joined",
    )
    manager = db.relationship(
        "User",
        foreign_keys=[manager_id],
        back_populates="managed_employees",
        lazy="joined",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "manager_id": self.manager_id,
        }

    def __repr__(self) -> str:
        return f"<EmployeeProfile user_id={self.user_id} manager_id={self.manager_id}>"
