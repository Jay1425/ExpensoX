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
	budgets = db.relationship("Budget", back_populates="company", lazy=True)

	def __repr__(self) -> str:  # pragma: no cover - debug helper
		return f"<Company {self.name} ({self.currency})>"


class User(db.Model):
	__tablename__ = "users"

	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(120), nullable=False)
	email = db.Column(db.String(120), unique=True, nullable=False, index=True)
	password_hash = db.Column(db.String(255), nullable=False)
	role = db.Column(db.String(50), default="Employee", nullable=False)
	company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
	is_manager_approver = db.Column(db.Boolean, default=False, nullable=False)
	manager_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
	is_verified = db.Column(db.Boolean, default=False, nullable=False)
	otp_code = db.Column(db.String(6), nullable=True)
	otp_expiry = db.Column(db.DateTime, nullable=True)
	created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

	company = db.relationship("Company", back_populates="users", lazy=True)
	manager = db.relationship("User", remote_side=[id], backref="direct_reports")
	expenses = db.relationship("Expense", back_populates="submitter", foreign_keys="Expense.submitted_by_user_id", lazy=True)
	approvals = db.relationship("Expense", back_populates="approver", foreign_keys="Expense.approved_by_user_id", lazy=True)
	approval_histories = db.relationship("ApprovalHistory", back_populates="approver", lazy=True)

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
	budgets = db.relationship("Budget", back_populates="category", lazy=True)

	def __repr__(self) -> str:  # pragma: no cover
		return f"<Category {self.name} company={self.company_id}>"


class Budget(db.Model):
	__tablename__ = "budgets"

	id = db.Column(db.Integer, primary_key=True)
	company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
	category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
	amount = db.Column(db.Numeric(12, 2), nullable=False)
	currency = db.Column(db.String(10), nullable=False)
	period_start = db.Column(db.Date, nullable=False)
	period_end = db.Column(db.Date, nullable=False)
	description = db.Column(db.String(255), nullable=True)
	created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
	updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

	company = db.relationship("Company", back_populates="budgets", lazy=True)
	category = db.relationship("Category", back_populates="budgets", lazy=True)

	def __repr__(self) -> str:  # pragma: no cover
		return f"<Budget company={self.company_id} category={self.category_id} amount={self.amount}>"


class ExpenseStatus(Enum):
	PENDING = "PENDING"
	IN_PROGRESS = "IN_PROGRESS"
	APPROVED = "APPROVED"
	REJECTED = "REJECTED"


class ApprovalFlow(db.Model):
	__tablename__ = "approval_flows"

	id = db.Column(db.Integer, primary_key=True)
	company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
	step_number = db.Column(db.Integer, nullable=False)
	approver_role = db.Column(db.String(50), nullable=True)
	approver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
	sequence_order = db.Column(db.Integer, nullable=False)
	created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

	company = db.relationship("Company", lazy=True)
	approver = db.relationship("User", lazy=True)

	def __repr__(self) -> str:  # pragma: no cover
		return f"<ApprovalFlow step={self.step_number} company={self.company_id}>"


class ApprovalRule(db.Model):
	__tablename__ = "approval_rules"

	id = db.Column(db.Integer, primary_key=True)
	company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
	rule_type = db.Column(db.String(50), nullable=False)  # percentage, specific, hybrid
	threshold_percent = db.Column(db.Float, nullable=True)
	specific_approver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
	hybrid_logic = db.Column(db.String(255), nullable=True)
	created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

	company = db.relationship("Company", lazy=True)
	specific_approver = db.relationship("User", lazy=True)

	def __repr__(self) -> str:  # pragma: no cover
		return f"<ApprovalRule {self.rule_type} company={self.company_id}>"


class ApprovalHistory(db.Model):
	__tablename__ = "approval_histories"

	id = db.Column(db.Integer, primary_key=True)
	expense_id = db.Column(db.Integer, db.ForeignKey("expenses.id"), nullable=False)
	approver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
	action = db.Column(db.String(20), nullable=False)  # Approved, Rejected
	comment = db.Column(db.Text, nullable=True)
	action_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

	expense = db.relationship("Expense", backref="approval_history", lazy=True)
	approver = db.relationship("User", back_populates="approval_histories", lazy=True)

	def __repr__(self) -> str:  # pragma: no cover
		return f"<ApprovalHistory {self.action} expense={self.expense_id}>"


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
	approval_flow_id = db.Column(db.Integer, db.ForeignKey("approval_flows.id"), nullable=True)
	current_approver_step = db.Column(db.Integer, default=1, nullable=True)

	company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
	category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
	submitted_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
	approved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

	company = db.relationship("Company", back_populates="expenses", lazy=True)
	category = db.relationship("Category", back_populates="expenses", lazy=True)
	submitter = db.relationship("User", back_populates="expenses", foreign_keys=[submitted_by_user_id], lazy=True)
	approver = db.relationship("User", back_populates="approvals", foreign_keys=[approved_by_user_id], lazy=True)
	approval_flow = db.relationship("ApprovalFlow", lazy=True)

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
