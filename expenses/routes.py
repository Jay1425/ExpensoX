from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask import flash, redirect, render_template, request, session, url_for

from auth.models import get_user_by_id
from database.models import Category, Expense, ExpenseStatus, db

from . import expenses_bp
from .forms import ExpenseDecisionForm, ExpenseForm


def _current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(user_id)


def _require_login():
    user = _current_user()
    if not user:
        flash("Please log in to access expenses.", "warning")
    return user


def _ensure_company_categories(company) -> None:
    if not company.categories:
        default_category = Category(name="General", description="Default category", company=company)
        db.session.add(default_category)
        db.session.commit()


def _populate_expense_form(form: ExpenseForm, company) -> None:
    form.currency.choices = [(company.currency, company.currency)]
    categories = Category.query.filter_by(company_id=company.id).order_by(Category.name.asc()).all()
    form.category.choices = [(str(cat.id), cat.name) for cat in categories]


@expenses_bp.route("/expenses", methods=["GET"])
def list_expenses():
    user = _require_login()
    if not user:
        return redirect(url_for("auth.login"))

    query = Expense.query.filter_by(submitted_by_user_id=user.id).order_by(Expense.submitted_at.desc())
    stats = {
        "pending": query.filter(Expense.status == ExpenseStatus.PENDING).count(),
        "approved": query.filter(Expense.status == ExpenseStatus.APPROVED).count(),
        "rejected": query.filter(Expense.status == ExpenseStatus.REJECTED).count(),
    }
    expenses = query.all()

    return render_template(
        "employee/expenses.html",
        expenses=expenses,
        stats=stats,
    )


@expenses_bp.route("/expenses/new", methods=["GET", "POST"])
def submit_expense():
    user = _require_login()
    if not user:
        return redirect(url_for("auth.login"))

    company = user.company
    if not company:
        flash("You are not associated with a company yet.", "error")
        return redirect(url_for("auth.dashboard"))

    _ensure_company_categories(company)

    form = ExpenseForm()
    _populate_expense_form(form, company)

    if request.method == "GET" and not form.currency.data:
        form.currency.data = company.currency

    if form.validate_on_submit():
        expense = Expense(
            title=form.title.data,
            description=form.description.data,
            amount=form.amount.data,
            currency=form.currency.data,
            spent_at=form.spent_at.data,
            receipt_url=form.receipt_url.data or None,
            company=company,
            submitter=user,
            category_id=int(form.category.data),
        )
        db.session.add(expense)
        db.session.commit()
        flash("Expense submitted for approval.", "success")
        return redirect(url_for("expenses.list_expenses"))

    return render_template("employee/submit_expense.html", form=form)


@expenses_bp.route("/manager/expenses", methods=["GET"])
def manager_pending_expenses():
    user = _require_login()
    if not user:
        return redirect(url_for("auth.login"))

    if user.role not in {"Manager", "Admin"}:
        flash("You do not have permission to view approvals.", "error")
        return redirect(url_for("expenses.list_expenses"))

    pending_expenses = (
        Expense.query.filter_by(company_id=user.company_id, status=ExpenseStatus.PENDING)
        .order_by(Expense.submitted_at.asc())
        .all()
    )

    today = date.today()
    stats = {
        "total": len(pending_expenses),
        "today": sum(1 for expense in pending_expenses if expense.submitted_at.date() == today),
        "overdue": sum(1 for expense in pending_expenses if expense.submitted_at.date() < today),
        "total_amount": sum((expense.amount for expense in pending_expenses), Decimal("0.00")),
    }

    return render_template("manager/pending_approvals.html", expenses=pending_expenses, stats=stats)


@expenses_bp.route("/manager/expenses/<int:expense_id>", methods=["GET", "POST"])
def manager_expense_detail(expense_id: int):
    user = _require_login()
    if not user:
        return redirect(url_for("auth.login"))

    if user.role not in {"Manager", "Admin"}:
        flash("You do not have permission to approve expenses.", "error")
        return redirect(url_for("expenses.list_expenses"))

    expense = Expense.query.filter_by(id=expense_id, company_id=user.company_id).first()
    if not expense:
        flash("Expense not found.", "error")
        return redirect(url_for("expenses.manager_pending_expenses"))

    form = ExpenseDecisionForm()

    if form.validate_on_submit():
        notes = form.notes.data.strip() if form.notes.data else None
        if form.decision.data == "approve":
            expense.mark_approved(user, notes)
            flash("Expense approved.", "success")
        else:
            expense.mark_rejected(user, notes)
            flash("Expense rejected.", "info")
        db.session.commit()
        return redirect(url_for("expenses.manager_pending_expenses"))

    return render_template("manager/approval_detail.html", expense=expense, form=form)