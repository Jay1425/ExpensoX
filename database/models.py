from datetime import datetime

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

	def set_password(self, password: str) -> None:
		self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

	def check_password(self, password: str) -> bool:
		return bcrypt.check_password_hash(self.password_hash, password)

	def clear_otp(self) -> None:
		self.otp_code = None
		self.otp_expiry = None

	def __repr__(self) -> str:  # pragma: no cover - debug helper
		return f"<User {self.email} verified={self.is_verified}>"
