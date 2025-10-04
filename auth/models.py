from datetime import datetime, timedelta
from typing import Optional

from flask import current_app

from database.models import Company, User, db


def get_user_by_email(email: str) -> Optional[User]:
	return User.query.filter_by(email=email).first()


def get_user_by_id(user_id: int) -> Optional[User]:
	return User.query.get(user_id)


def create_company(name: str, country: str, currency: str) -> Company:
	company = Company(name=name, country=country, currency=currency)
	db.session.add(company)
	return company


def first_company() -> Optional[Company]:
	return Company.query.order_by(Company.created_at.asc()).first()


def save_user(
	*,
	name: str,
	email: str,
	raw_password: str,
	role: str,
	company: Optional[Company] = None,
) -> User:
	user = User(name=name, email=email, role=role)
	if company:
		user.company = company
	user.set_password(raw_password)
	db.session.add(user)
	return user


def assign_otp(user: User, otp_code: str) -> None:
	expiry_minutes = current_app.config.get("OTP_EXPIRY_MINUTES", 5)
	user.otp_code = otp_code
	user.otp_expiry = datetime.utcnow() + timedelta(minutes=expiry_minutes)


def is_otp_valid(user: User, submitted_code: str) -> bool:
	if not user.otp_code or not user.otp_expiry:
		return False
	if datetime.utcnow() > user.otp_expiry:
		return False
	return user.otp_code == submitted_code


def clear_otp(user: User) -> None:
	user.clear_otp()


def commit_changes() -> None:
	db.session.commit()
