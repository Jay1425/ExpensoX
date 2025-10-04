from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length


class SignupForm(FlaskForm):
	name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
	email = StringField(
		"Email",
		validators=[DataRequired(), Email(), Length(max=120)],
	)
	company_name = StringField("Company Name", validators=[DataRequired(), Length(max=120)])
	password = PasswordField(
		"Password",
		validators=[DataRequired(), Length(min=8, message="Use at least 8 characters.")],
	)
	confirm_password = PasswordField(
		"Confirm Password",
		validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
	)
	country = SelectField("Country", validators=[DataRequired()], choices=[])
	submit = SubmitField("Create Account")


class LoginForm(FlaskForm):
	email = StringField("Email", validators=[DataRequired(), Email()])
	password = PasswordField("Password", validators=[DataRequired()])
	submit = SubmitField("Login")


class OTPForm(FlaskForm):
	otp_code = StringField(
		"One-Time Password",
		validators=[DataRequired(), Length(min=6, max=6, message="Enter the 6-digit code.")],
	)
	submit = SubmitField("Verify OTP")


class ForgotPasswordForm(FlaskForm):
	email = StringField("Email", validators=[DataRequired(), Email()])
	submit = SubmitField("Send OTP")


class ResetPasswordForm(FlaskForm):
	otp_code = StringField(
		"One-Time Password",
		validators=[DataRequired(), Length(min=6, max=6)],
	)
	password = PasswordField(
		"New Password",
		validators=[DataRequired(), Length(min=8)],
	)
	confirm_password = PasswordField(
		"Confirm New Password",
		validators=[DataRequired(), EqualTo("password")],
	)
	submit = SubmitField("Reset Password")
