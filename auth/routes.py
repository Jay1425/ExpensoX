from datetime import datetime
from decimal import Decimal

from flask import (
	current_app,
	flash,
	redirect,
	render_template,
	request,
	session,
	url_for,
)
from sqlalchemy import func

from . import auth_bp
from .forms import ForgotPasswordForm, LoginForm, OTPForm, ResetPasswordForm, SignupForm
from .models import (
	assign_otp,
	clear_otp,
	commit_changes,
	create_company,
	first_company,
	get_user_by_email,
	get_user_by_id,
	is_otp_valid,
	save_user,
)
from database.models import Expense, ExpenseStatus, User, db
from .utils import (
	OTPDeliveryError,
	generate_otp,
	get_country_choices,
	get_currency_for_country,
	send_otp_email,
)


@auth_bp.before_app_request
def ensure_country_choices_cached() -> None:
	"""Prime the country choices cache before first request."""

	if request.endpoint and request.endpoint.startswith("auth."):
		# Access to ensure mapping is loaded; errors handled inside utility.
		get_country_choices()


@auth_bp.route("/", methods=["GET"])
def index():
	return render_template("auth/index.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
	form = SignupForm()
	form.country.choices = get_country_choices()

	if form.validate_on_submit():
		existing_user = get_user_by_email(form.email.data.lower())
		if existing_user:
			flash("Email already registered. Please log in.", "error")
			return redirect(url_for("auth.login"))

		currency = get_currency_for_country(form.country.data)
		company = create_company(form.company_name.data, form.country.data, currency)

		user = save_user(
			name=form.name.data,
			email=form.email.data.lower(),
			raw_password=form.password.data,
			role="Admin",
			company=company,
		)

		otp_code = generate_otp()
		assign_otp(user, otp_code)

		try:
			send_otp_email(user.email, otp_code, "account verification")
		except OTPDeliveryError as exc:
			db.session.rollback()
			flash(
				"We couldn't send the verification email. Please check the mail settings and try again.",
				"error",
			)
			current_app.logger.error("Signup OTP email failed: %s", exc)
			return redirect(url_for("auth.signup"))

		commit_changes()
		session["pending_user_id"] = user.id
		flash("Account created! Enter the OTP we sent to verify your email.", "success")
		return redirect(url_for("auth.otp_verify"))

	return render_template("auth/signup.html", form=form)


@auth_bp.route("/otp-verify", methods=["GET", "POST"])
def otp_verify():
	pending_user_id = session.get("pending_user_id")
	if not pending_user_id:
		flash("Nothing to verify right now. Log in or sign up first.", "info")
		return redirect(url_for("auth.login"))

	user = get_user_by_id(pending_user_id)
	if not user:
		session.pop("pending_user_id", None)
		flash("We couldn't find that account. Please sign up again.", "error")
		return redirect(url_for("auth.signup"))

	form = OTPForm()
	if form.validate_on_submit():
		submitted_code = form.otp_code.data.strip()
		if is_otp_valid(user, submitted_code):
			user.is_verified = True
			clear_otp(user)
			commit_changes()
			session.pop("pending_user_id", None)
			flash("Email verified! You can log in now.", "success")
			return redirect(url_for("auth.login"))

		flash("Invalid or expired OTP. Try again.", "error")

	return render_template(
		"auth/otp_verify.html",
		form=form,
		heading="Verify your account",
		description="Enter the 6-digit code we sent to activate your account.",
		reset_mode=False,
	)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
	form = LoginForm()

	if form.validate_on_submit():
		user = get_user_by_email(form.email.data.lower())
		if not user or not user.check_password(form.password.data):
			flash("Incorrect email or password.", "error")
		elif not user.is_verified:
			session["pending_user_id"] = user.id
			flash("Please verify your email before logging in.", "warning")
			return redirect(url_for("auth.otp_verify"))
		else:
			session["user_id"] = user.id
			flash("Welcome back!", "success")
			return redirect(url_for("auth.dashboard"))

	return render_template("auth/login.html", form=form)


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
	form = ForgotPasswordForm()

	if form.validate_on_submit():
		user = get_user_by_email(form.email.data.lower())
		if user:
			otp_code = generate_otp()
			assign_otp(user, otp_code)
			try:
				send_otp_email(user.email, otp_code, "password reset")
			except OTPDeliveryError as exc:
				db.session.rollback()
				flash(
					"We couldn't send the reset email. Update the SMTP settings and try again.",
					"error",
				)
				current_app.logger.error("Password reset OTP email failed: %s", exc)
				return redirect(url_for("auth.forgot_password"))

			commit_changes()
			session["reset_user_id"] = user.id
			flash("We've sent you a reset OTP. Enter it below.", "info")
			return redirect(url_for("auth.reset_password"))

		flash("If that email exists, we'll send an OTP shortly.", "info")

	return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
	user_id = session.get("reset_user_id")
	if not user_id:
		flash("Start by requesting a password reset.", "warning")
		return redirect(url_for("auth.forgot_password"))

	user = get_user_by_id(user_id)
	if not user:
		session.pop("reset_user_id", None)
		flash("Something went wrong. Please request a new reset link.", "error")
		return redirect(url_for("auth.forgot_password"))

	form = ResetPasswordForm()
	if form.validate_on_submit():
		if is_otp_valid(user, form.otp_code.data.strip()):
			user.set_password(form.password.data)
			user.is_verified = True
			clear_otp(user)
			commit_changes()
			session.pop("reset_user_id", None)
			flash("Password updated! Log in with your new password.", "success")
			return redirect(url_for("auth.login"))

		flash("Invalid or expired OTP. Please try again.", "error")

	return render_template(
		"auth/otp_verify.html",
		form=form,
		heading="Reset your password",
		description="Enter the OTP we sent, then choose a new password.",
		reset_mode=True,
	)


@auth_bp.route("/dashboard", methods=["GET"])
def dashboard():
	user_id = session.get("user_id")
	if not user_id:
		flash("Please log in to access the dashboard.", "warning")
		return redirect(url_for("auth.login"))

	user = get_user_by_id(user_id)
	if not user:
		session.pop("user_id", None)
		flash("Account not found. Please log in again.", "error")
		return redirect(url_for("auth.login"))

	company = user.company
	currency = company.currency if company else current_app.config.get("DEFAULT_CURRENCY", "USD")
	role = (user.role or "Employee").lower()

	# Employee-focused summary
	employee_summary = None
	if role not in {"manager", "admin"}:
		employee_query = Expense.query.filter_by(submitted_by_user_id=user.id)
		recent_expenses = employee_query.order_by(Expense.submitted_at.desc()).limit(5).all()
		status_counts = {status.name.lower(): 0 for status in ExpenseStatus}
		for status, count in (
			db.session.query(Expense.status, func.count(Expense.id))
			.filter(Expense.submitted_by_user_id == user.id)
			.group_by(Expense.status)
			.all()
		):
			status_counts[status.name.lower()] = count
		total_amount = (
			db.session.query(func.coalesce(func.sum(Expense.amount), 0))
			.filter(Expense.submitted_by_user_id == user.id)
			.scalar()
		)
		last_submitted = recent_expenses[0] if recent_expenses else None
		employee_summary = {
			"recent_expenses": recent_expenses,
			"status_counts": status_counts,
			"total_amount": Decimal(total_amount or 0),
			"total_count": sum(status_counts.values()),
			"last_submitted": last_submitted,
		}

	# Manager/Admin summary
	manager_summary = None
	if role in {"manager", "admin"} and company:
		company_expenses = Expense.query.filter_by(company_id=company.id)
		pending_expenses = company_expenses.filter(Expense.status == ExpenseStatus.PENDING)
		recent_team_expenses = company_expenses.order_by(Expense.submitted_at.desc()).limit(5).all()
		status_counts = {status.name.lower(): 0 for status in ExpenseStatus}
		for status, count in (
			db.session.query(Expense.status, func.count(Expense.id))
			.filter(Expense.company_id == company.id)
			.group_by(Expense.status)
			.all()
		):
			status_counts[status.name.lower()] = count
		month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
		monthly_total = (
			db.session.query(func.coalesce(func.sum(Expense.amount), 0))
			.filter(Expense.company_id == company.id, Expense.submitted_at >= month_start)
			.scalar()
		)
		pending_amount = (
			db.session.query(func.coalesce(func.sum(Expense.amount), 0))
			.filter(Expense.company_id == company.id, Expense.status == ExpenseStatus.PENDING)
			.scalar()
		)
		processed_expenses = company_expenses.filter(Expense.decided_at.isnot(None)).all()
		if processed_expenses:
			processing_days = [
				(expense.decided_at - expense.submitted_at).total_seconds() / 86400
				for expense in processed_expenses
				if expense.decided_at >= expense.submitted_at
			]
			avg_processing_days = round(sum(processing_days) / len(processing_days), 1) if processing_days else None
		else:
			avg_processing_days = None
		team_members = (
			User.query.filter(User.company_id == company.id)
			.order_by(User.name.asc())
			.limit(8)
			.all()
		)
		manager_summary = {
			"pending_total": pending_expenses.count(),
			"pending_amount": Decimal(pending_amount or 0),
			"status_counts": status_counts,
			"recent_expenses": recent_team_expenses,
			"team_size": User.query.filter(User.company_id == company.id).count(),
			"team_members": team_members,
			"monthly_total": Decimal(monthly_total or 0),
			"avg_processing_days": avg_processing_days,
		}

	dashboard_context = {
		"first_name": user.name.split()[0] if user.name else "there",
		"role": user.role,
		"company": company,
		"currency": currency,
		"employee": employee_summary,
		"manager": manager_summary,
	}

	return render_template(
		"auth/index.html",
		user=user,
		dashboard=True,
		dashboard_context=dashboard_context,
	)


@auth_bp.route("/logout", methods=["POST"])
def logout():
	session.pop("user_id", None)
	flash("Logged out successfully.", "info")
	return redirect(url_for("auth.login"))
