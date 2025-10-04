from datetime import datetime
from enum import Enum

from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()
bcrypt = Bcrypt()


class Company(db.Model):
	__tablename__ = "companies"

	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(120), nullable=False)
	country = db.Column(db.String(120), nullable=False)
	currency = db.Column(db.String(10), nullable=False)
	created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

	users = db.relationship("User", back_populates="company", lazy=True)
	categories = db.relationship("Category", back_populates="company", lazy=True)
	expenses = db.relationship("Expense", back_populates="company", lazy=True)

	def __repr__(self) -> str:  # pragma: no cover - debug helper
		return f"<Company {self.name} ({self.currency})>"


class User(db.Model):
	__tablename__ = "users"

	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(120), nullable=False)
	email = db.Column(db.String(120), unique=True, nullable=False, index=True)
	password_hash = db.Column(db.String(255), nullable=False)
	role = db.Column(db.String(50), default="Admin", nullable=False)
	company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
	is_verified = db.Column(db.Boolean, default=False, nullable=False)
	otp_code = db.Column(db.String(6), nullable=True)
	otp_expiry = db.Column(db.DateTime, nullable=True)
	created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

	company = db.relationship("Company", back_populates="users", lazy=True)
	expenses = db.relationship("Expense", back_populates="submitter", foreign_keys="Expense.submitted_by_user_id", lazy=True)
	approvals = db.relationship("Expense", back_populates="approver", foreign_keys="Expense.approved_by_user_id", lazy=True)

	def set_password(self, password: str) -> None:
		self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

	def check_password(self, password: str) -> bool:
		return bcrypt.check_password_hash(self.password_hash, password)

	def clear_otp(self) -> None:
		self.otp_code = None
		self.otp_expiry = None

	def __repr__(self) -> str:  # pragma: no cover - debug helper
		return f"<User {self.email} verified={self.is_verified}>"


class Category(db.Model):
	__tablename__ = "categories"

	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(120), nullable=False)
	description = db.Column(db.String(255), nullable=True)
	company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
	created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
	updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

	company = db.relationship("Company", back_populates="categories", lazy=True)
	expenses = db.relationship("Expense", back_populates="category", lazy=True)

	def __repr__(self) -> str:  # pragma: no cover
		return f"<Category {self.name} company={self.company_id}>"


class ExpenseStatus(Enum):
	PENDING = "PENDING"
	APPROVED = "APPROVED"
	REJECTED = "REJECTED"


class Expense(db.Model):
	__tablename__ = "expenses"

	id = db.Column(db.Integer, primary_key=True)
	title = db.Column(db.String(150), nullable=False)
	description = db.Column(db.Text, nullable=True)
	amount = db.Column(db.Numeric(10, 2), nullable=False)
	currency = db.Column(db.String(10), nullable=False)
	status = db.Column(db.Enum(ExpenseStatus), default=ExpenseStatus.PENDING, nullable=False)
	receipt_url = db.Column(db.String(255), nullable=True)
	spent_at = db.Column(db.Date, nullable=False)
	submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
	decided_at = db.Column(db.DateTime, nullable=True)
	manager_notes = db.Column(db.Text, nullable=True)

	company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
	category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
	submitted_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
	approved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

	company = db.relationship("Company", back_populates="expenses", lazy=True)
	category = db.relationship("Category", back_populates="expenses", lazy=True)
	submitter = db.relationship("User", back_populates="expenses", foreign_keys=[submitted_by_user_id], lazy=True)
	approver = db.relationship("User", back_populates="approvals", foreign_keys=[approved_by_user_id], lazy=True)

	def mark_approved(self, approver: "User", notes: str | None = None) -> None:
		self.status = ExpenseStatus.APPROVED
		self.approver = approver
		self.decided_at = datetime.utcnow()
		self.manager_notes = notes

	def mark_rejected(self, approver: "User", notes: str | None = None) -> None:
		self.status = ExpenseStatus.REJECTED
		self.approver = approver
		self.decided_at = datetime.utcnow()
		self.manager_notes = notes

	def __repr__(self) -> str:  # pragma: no cover
		return f"<Expense {self.title} {self.status.value}>"
