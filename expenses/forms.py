from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import DecimalField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.fields import DateField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError


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


class CategoryForm(FlaskForm):
    name = StringField("Category name", validators=[DataRequired(), Length(max=120)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Save category")


class CategoryDeleteForm(FlaskForm):
    submit = SubmitField("Delete")


class BudgetForm(FlaskForm):
    category = SelectField("Category", validators=[DataRequired()], choices=[], coerce=int)
    amount = DecimalField(
        "Budget amount",
        places=2,
        rounding=None,
        validators=[DataRequired(), NumberRange(min=Decimal("0.01"))],
    )
    period_start = DateField("Period start", validators=[DataRequired()])
    period_end = DateField("Period end", validators=[DataRequired()])
    description = TextAreaField("Description", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Save budget")

    def validate_period_end(self, field):  # pylint: disable=missing-docstring
        if self.period_start.data and field.data and field.data < self.period_start.data:
            raise ValidationError("Period end must be after the start date.")


class BudgetDeleteForm(FlaskForm):
    submit = SubmitField("Delete")
