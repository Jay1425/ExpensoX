from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import DecimalField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.fields import DateField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class ExpenseForm(FlaskForm):
    title = StringField("Expense title", validators=[DataRequired(), Length(max=150)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=500)])
    amount = DecimalField(
        "Amount",
        places=2,
        rounding=None,
        validators=[DataRequired(), NumberRange(min=Decimal("0.01"))],
    )
    currency = SelectField("Currency", validators=[DataRequired()], choices=[])
    category = SelectField("Category", validators=[DataRequired()], choices=[])
    spent_at = DateField("Date of expense", validators=[DataRequired()], default=date.today)
    receipt_url = StringField("Receipt URL", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Submit expense")


class ExpenseDecisionForm(FlaskForm):
    decision = SelectField(
        "Decision",
        validators=[DataRequired()],
        choices=[("approve", "Approve"), ("reject", "Reject")],
    )
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Update status")
