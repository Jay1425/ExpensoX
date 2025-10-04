from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from math import ceil

from flask import abort, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func, or_

from auth.models import get_user_by_id
from database.models import Budget, Category, Expense, ExpenseStatus, User, db, ApprovalFlow, ApprovalRule
from auth.utils import OTPDeliveryError, send_notification_email

from . import expenses_bp
from .forms import (
    BudgetDeleteForm,
    BudgetForm,
    CategoryDeleteForm,
    CategoryForm,
    ExpenseDecisionForm,
    ExpenseForm,
)


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

    base_query = Expense.query.filter_by(submitted_by_user_id=user.id)

    stats = {
        "pending": base_query.filter(Expense.status == ExpenseStatus.PENDING).count(),
        "approved": base_query.filter(Expense.status == ExpenseStatus.APPROVED).count(),
        "rejected": base_query.filter(Expense.status == ExpenseStatus.REJECTED).count(),
    }

    status_filter_raw = request.args.get("status", "").strip()
    search_query = request.args.get("q", "").strip()
    page = request.args.get("page", type=int, default=1)
    per_page = request.args.get("per_page", type=int, default=10)
    if page is None or page < 1:
        page = 1
    if per_page is None or per_page < 1:
        per_page = 10
    per_page = min(per_page, 50)

    filtered_query = base_query

    status_filter = None
    if status_filter_raw:
        status_key = status_filter_raw.strip().upper()
        if status_key in ExpenseStatus.__members__:
            status_filter = ExpenseStatus[status_key]
            filtered_query = filtered_query.filter(Expense.status == status_filter)

    if search_query:
        like_term = f"%{search_query}%"
        filtered_query = filtered_query.filter(
            or_(
                Expense.title.ilike(like_term),
                Expense.description.ilike(like_term),
                Expense.currency.ilike(like_term),
                Expense.category.has(Category.name.ilike(like_term)),
            )
        )

    filtered_query = filtered_query.order_by(Expense.submitted_at.desc())
    total = filtered_query.count()
    pages = max(1, ceil(total / per_page)) if total else 1
    if page > pages:
        page = pages
    offset = (page - 1) * per_page
    expenses = filtered_query.offset(offset).limit(per_page).all() if total else []

    pagination = {
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "has_prev": page > 1,
        "has_next": page < pages if pages else False,
        "prev_page": page - 1 if page > 1 else None,
        "next_page": page + 1 if pages and page < pages else None,
    }

    filters = {
        "status": status_filter.name if status_filter else "",
        "search": search_query,
    }

    return render_template(
        "employee/expenses.html",
        expenses=expenses,
        stats=stats,
        pagination=pagination,
        filters=filters,
        current_user=user,
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
        
        # Assign approval workflow based on rules
        approval_flow, initial_status = _assign_approval_workflow(expense, user)
        if approval_flow:
            expense.approval_flow_id = approval_flow.id
            expense.current_approver_step = approval_flow.step_number
            expense.status = initial_status
        
        db.session.add(expense)
        db.session.commit()
        flash("Expense submitted for approval.", "success")
        return redirect(url_for("expenses.list_expenses"))

    return render_template("employee/submit_expense.html", form=form, current_user=user)


@expenses_bp.route("/categories", methods=["GET", "POST"])
def manage_categories():
    user = _require_login()
    if not user:
        return redirect(url_for("auth.login"))

    if user.role not in {"Admin", "Manager"}:
        flash("You do not have permission to manage categories.", "error")
        return redirect(url_for("expenses.list_expenses"))

    company = user.company
    if not company:
        flash("You are not associated with a company yet.", "error")
        return redirect(url_for("auth.dashboard"))

    form = CategoryForm()
    delete_form = CategoryDeleteForm()

    if form.validate_on_submit():
        name = form.name.data.strip()
        description = form.description.data.strip() if form.description.data else None
        duplicate = (
            Category.query.filter(Category.company_id == company.id)
            .filter(func.lower(Category.name) == name.lower())
            .first()
        )
        if duplicate:
            flash("A category with that name already exists.", "warning")
        else:
            category = Category(name=name, description=description, company=company)
            db.session.add(category)
            db.session.commit()
            flash("Category added successfully.", "success")
            return redirect(url_for("expenses.manage_categories"))

    search_query = request.args.get("q", "").strip()
    categories_query = Category.query.filter_by(company_id=company.id)
    if search_query:
        like_term = f"%{search_query}%"
        categories_query = categories_query.filter(Category.name.ilike(like_term))

    categories = categories_query.order_by(Category.name.asc()).all()

    expense_counts: dict[int, int] = {}
    category_ids = [category.id for category in categories]
    if category_ids:
        for category_id, count in (
            db.session.query(Expense.category_id, func.count(Expense.id))
            .filter(Expense.category_id.in_(category_ids))
            .group_by(Expense.category_id)
            .all()
        ):
            expense_counts[category_id] = count

    form.submit.label.text = "Add category"

    return render_template(
        "admin/categories.html",
        form=form,
        delete_form=delete_form,
        categories=categories,
        expense_counts=expense_counts,
        search_query=search_query,
        current_user=user,
    )


@expenses_bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
def edit_category(category_id: int):
    user = _require_login()
    if not user:
        return redirect(url_for("auth.login"))

    if user.role not in {"Admin", "Manager"}:
        flash("You do not have permission to manage categories.", "error")
        return redirect(url_for("expenses.list_expenses"))

    company = user.company
    if not company:
        flash("You are not associated with a company yet.", "error")
        return redirect(url_for("auth.dashboard"))

    category = Category.query.filter_by(id=category_id, company_id=company.id).first()
    if not category:
        abort(404)

    form = CategoryForm(obj=category)
    form.submit.label.text = "Update category"

    if form.validate_on_submit():
        name = form.name.data.strip()
        description = form.description.data.strip() if form.description.data else None
        duplicate = (
            Category.query.filter(Category.company_id == company.id)
            .filter(func.lower(Category.name) == name.lower(), Category.id != category.id)
            .first()
        )
        if duplicate:
            flash("Another category with that name already exists.", "warning")
        else:
            category.name = name
            category.description = description
            db.session.commit()
            flash("Category updated successfully.", "success")
            return redirect(url_for("expenses.manage_categories"))

    return render_template("admin/edit_category.html", form=form, category=category, current_user=user)


@expenses_bp.route("/categories/<int:category_id>/delete", methods=["POST"])
def delete_category(category_id: int):
    user = _require_login()
    if not user:
        return redirect(url_for("auth.login"))

    if user.role not in {"Admin", "Manager"}:
        flash("You do not have permission to manage categories.", "error")
        return redirect(url_for("expenses.list_expenses"))

    company = user.company
    if not company:
        flash("You are not associated with a company yet.", "error")
        return redirect(url_for("auth.dashboard"))

    category = Category.query.filter_by(id=category_id, company_id=company.id).first()
    if not category:
        abort(404)

    form = CategoryDeleteForm()
    if not form.validate_on_submit():
        flash("Invalid request.", "error")
        return redirect(url_for("expenses.manage_categories"))

    if category.expenses:
        flash("You cannot delete a category that still has expenses assigned.", "warning")
        return redirect(url_for("expenses.manage_categories"))

    db.session.delete(category)
    db.session.commit()
    flash("Category deleted successfully.", "success")
    return redirect(url_for("expenses.manage_categories"))


def _get_default_budget_period() -> tuple[date, date]:
    today = date.today()
    period_start = today.replace(day=1)
    last_day = monthrange(today.year, today.month)[1]
    period_end = period_start.replace(day=last_day)
    return period_start, period_end


@expenses_bp.route("/budgets", methods=["GET", "POST"])
def manage_budgets():
    user = _require_login()
    if not user:
        return redirect(url_for("auth.login"))

    if user.role not in {"Admin", "Manager"}:
        flash("You do not have permission to manage budgets.", "error")
        return redirect(url_for("expenses.list_expenses"))

    company = user.company
    if not company:
        flash("You are not associated with a company yet.", "error")
        return redirect(url_for("auth.dashboard"))

    categories = Category.query.filter_by(company_id=company.id).order_by(Category.name.asc()).all()
    form = BudgetForm()
    delete_form = BudgetDeleteForm()
    form.category.choices = [(category.id, category.name) for category in categories]

    if request.method == "GET" and categories:
        start_default, end_default = _get_default_budget_period()
        if not form.period_start.data:
            form.period_start.data = start_default
        if not form.period_end.data:
            form.period_end.data = end_default

    can_submit = bool(form.category.choices)
    if can_submit and form.validate_on_submit():
        category_id = form.category.data
        amount = form.amount.data
        period_start = form.period_start.data
        period_end = form.period_end.data
        description = form.description.data.strip() if form.description.data else None

        duplicate = (
            Budget.query.filter_by(company_id=company.id, category_id=category_id)
            .filter(Budget.period_start <= period_end, Budget.period_end >= period_start)
            .first()
        )
        if duplicate:
            flash("A budget for that category already covers this period.", "warning")
        else:
            budget = Budget(
                company=company,
                category_id=category_id,
                amount=amount,
                currency=company.currency,
                period_start=period_start,
                period_end=period_end,
                description=description,
            )
            db.session.add(budget)
            db.session.commit()
            flash("Budget saved successfully.", "success")
            return redirect(url_for("expenses.manage_budgets"))
    elif request.method == "POST" and not can_submit:
        flash("Add at least one category before creating budgets.", "warning")
        return redirect(url_for("expenses.manage_categories"))

    search_query = request.args.get("q", "").strip()
    budgets_query = Budget.query.filter_by(company_id=company.id).join(Category)
    if search_query:
        like_term = f"%{search_query}%"
        budgets_query = budgets_query.filter(Category.name.ilike(like_term))

    budgets = budgets_query.order_by(Budget.period_start.desc()).all()
    budget_rows = []
    for budget in budgets:
        spent_value = (
            db.session.query(func.coalesce(func.sum(Expense.amount), 0))
            .filter(
                Expense.company_id == company.id,
                Expense.category_id == budget.category_id,
                Expense.spent_at >= budget.period_start,
                Expense.spent_at <= budget.period_end,
                Expense.status != ExpenseStatus.REJECTED,
            )
            .scalar()
        )
        spent = Decimal(spent_value or 0)
        amount = Decimal(budget.amount or 0)
        remaining = amount - spent
        usage_percent = float(0)
        if amount > 0:
            usage_percent = float(min(100, max(0, (spent / amount) * 100)))

        budget_rows.append(
            {
                "budget": budget,
                "spent": spent,
                "remaining": remaining,
                "usage_percent": round(usage_percent, 1) if amount > 0 else 0,
                "is_over_limit": remaining < 0,
            }
        )

    form.submit.label.text = "Add budget"

    return render_template(
        "admin/budgets.html",
        form=form,
        delete_form=delete_form,
        budgets=budget_rows,
        categories=categories,
        company_currency=company.currency,
        search_query=search_query,
        current_user=user,
    )


@expenses_bp.route("/budgets/<int:budget_id>/edit", methods=["GET", "POST"])
def edit_budget(budget_id: int):
    user = _require_login()
    if not user:
        return redirect(url_for("auth.login"))

    if user.role not in {"Admin", "Manager"}:
        flash("You do not have permission to manage budgets.", "error")
        return redirect(url_for("expenses.list_expenses"))

    company = user.company
    if not company:
        flash("You are not associated with a company yet.", "error")
        return redirect(url_for("auth.dashboard"))

    budget = Budget.query.filter_by(id=budget_id, company_id=company.id).first()
    if not budget:
        abort(404)

    categories = Category.query.filter_by(company_id=company.id).order_by(Category.name.asc()).all()
    form = BudgetForm(obj=budget)
    form.category.choices = [(category.id, category.name) for category in categories]
    form.submit.label.text = "Update budget"

    if form.validate_on_submit():
        category_id = form.category.data
        amount = form.amount.data
        period_start = form.period_start.data
        period_end = form.period_end.data
        description = form.description.data.strip() if form.description.data else None

        duplicate = (
            Budget.query.filter_by(company_id=company.id, category_id=category_id)
            .filter(Budget.id != budget.id)
            .filter(Budget.period_start <= period_end, Budget.period_end >= period_start)
            .first()
        )
        if duplicate:
            flash("Another budget already covers that time period for this category.", "warning")
        else:
            budget.category_id = category_id
            budget.amount = amount
            budget.period_start = period_start
            budget.period_end = period_end
            budget.description = description
            db.session.commit()
            flash("Budget updated successfully.", "success")
            return redirect(url_for("expenses.manage_budgets"))

    return render_template(
        "admin/edit_budget.html",
        form=form,
        budget=budget,
        categories=categories,
        company_currency=company.currency,
        current_user=user,
    )


@expenses_bp.route("/budgets/<int:budget_id>/delete", methods=["POST"])
def delete_budget(budget_id: int):
    user = _require_login()
    if not user:
        return redirect(url_for("auth.login"))

    if user.role not in {"Admin", "Manager"}:
        flash("You do not have permission to manage budgets.", "error")
        return redirect(url_for("expenses.list_expenses"))

    company = user.company
    if not company:
        flash("You are not associated with a company yet.", "error")
        return redirect(url_for("auth.dashboard"))

    budget = Budget.query.filter_by(id=budget_id, company_id=company.id).first()
    if not budget:
        abort(404)

    form = BudgetDeleteForm()
    if not form.validate_on_submit():
        flash("Invalid request.", "error")
        return redirect(url_for("expenses.manage_budgets"))

    db.session.delete(budget)
    db.session.commit()
    flash("Budget removed successfully.", "success")
    return redirect(url_for("expenses.manage_budgets"))


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

    status_filter_raw = request.args.get("status", "PENDING").strip().upper()
    search_query = request.args.get("q", "").strip()
    page = request.args.get("page", type=int, default=1)
    per_page = request.args.get("per_page", type=int, default=10)
    if page is None or page < 1:
        page = 1
    if per_page is None or per_page < 1:
        per_page = 10
    per_page = min(per_page, 50)

    filtered_query = Expense.query.filter_by(company_id=user.company_id)

    status_filter = None
    if status_filter_raw and status_filter_raw != "ALL":
        if status_filter_raw in ExpenseStatus.__members__:
            status_filter = ExpenseStatus[status_filter_raw]
            filtered_query = filtered_query.filter(Expense.status == status_filter)
        else:
            status_filter = ExpenseStatus.PENDING
            filtered_query = filtered_query.filter(Expense.status == status_filter)
    elif status_filter_raw == "ALL":
        status_filter = None
    else:
        status_filter = ExpenseStatus.PENDING
        filtered_query = filtered_query.filter(Expense.status == status_filter)

    if search_query:
        like_term = f"%{search_query}%"
        filtered_query = filtered_query.filter(
            or_(
                Expense.title.ilike(like_term),
                Expense.description.ilike(like_term),
                Expense.currency.ilike(like_term),
                Expense.submitter.has(User.name.ilike(like_term)),
            )
        )

    filtered_query = filtered_query.order_by(Expense.submitted_at.desc())
    total = filtered_query.count()
    pages = max(1, ceil(total / per_page)) if total else 1
    if page > pages:
        page = pages
    offset = (page - 1) * per_page
    expenses = filtered_query.offset(offset).limit(per_page).all() if total else []

    pagination = {
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "has_prev": page > 1,
        "has_next": page < pages if pages else False,
        "prev_page": page - 1 if page > 1 else None,
        "next_page": page + 1 if pages and page < pages else None,
    }

    filters = {
        "status": status_filter.name if status_filter else ("ALL" if status_filter_raw == "ALL" else ""),
        "search": search_query,
    }

    return render_template(
        "manager/pending_approvals.html",
        expenses=expenses,
        stats=stats,
        pagination=pagination,
        filters=filters,
        current_user=user,
    )


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
        decision = form.decision.data
        if decision == "approve":
            expense.mark_approved(user, notes)
            flash("Expense approved.", "success")
        else:
            expense.mark_rejected(user, notes)
            flash("Expense rejected.", "info")
        db.session.commit()

        if expense.submitter and expense.submitter.email:
            submitter_name = expense.submitter.name or "there"
            first_name = submitter_name.split()[0]
            status_label = expense.status.name.replace("_", " ").title()
            decision_text = "approved" if decision == "approve" else "rejected"
            approver_name = user.name or "your manager"
            notes_text = f"\n\nManager notes:\n{notes}" if notes else ""
            body = (
                f"Hi {first_name},\n\n"
                f"Your expense '{expense.title}' submitted on {expense.submitted_at.strftime('%b %d, %Y')} "
                f"has been {decision_text} by {approver_name}.\n"
                f"Status: {status_label}.\n"
                f"Amount: {expense.amount} {expense.currency}.\n"
                f"Spent on: {expense.spent_at.strftime('%b %d, %Y')}."
                f"{notes_text}\n\n"
                "Sign in to ExpensoX to review the full details.\n\n"
                "— ExpensoX"
            )
            subject = f"Expense '{expense.title}' was {decision_text}"
            try:
                send_notification_email(expense.submitter.email, subject, body)
            except OTPDeliveryError as exc:  # pragma: no cover - SMTP dependent
                current_app.logger.warning(
                    "Failed to send expense decision email for expense %s: %s", expense.id, exc
                )

        return redirect(url_for("expenses.manager_pending_expenses"))

    return render_template("manager/approval_detail.html", expense=expense, form=form, current_user=user)


def _assign_approval_workflow(expense, user):
    """
    Assign approval workflow to an expense based on company rules.
    Returns (approval_flow, initial_status) tuple.
    """
    company_id = user.company_id
    
    # Get approval rules for the company
    approval_rules = ApprovalRule.query.filter_by(company_id=company_id).all()
    
    if not approval_rules:
        # No rules defined, use simple manager approval if user has a manager
        if user.manager_id:
            # Create or get a simple manager approval flow
            flow = ApprovalFlow.query.filter_by(
                company_id=company_id,
                step_number=1,
                approver_id=user.manager_id
            ).first()
            
            if not flow:
                flow = ApprovalFlow(
                    company_id=company_id,
                    step_number=1,
                    approver_id=user.manager_id,
                    sequence_order=1
                )
                db.session.add(flow)
                db.session.flush()  # Get the ID
            
            return flow, ExpenseStatus.IN_PROGRESS
        else:
            # No manager, auto-approve or keep pending
            return None, ExpenseStatus.PENDING
    
    # Apply approval rules
    for rule in approval_rules:
        if rule.rule_type == 'percentage':
            # Check if expense amount is above threshold percentage of some budget
            if rule.threshold_percent:
                # For simplicity, we'll check against a monthly budget limit
                # In practice, this could be more sophisticated
                threshold_amount = Decimal('1000.00') * (rule.threshold_percent / 100)
                if expense.amount >= threshold_amount:
                    # Find the first approval flow for this company
                    flow = ApprovalFlow.query.filter_by(company_id=company_id)\
                        .order_by(ApprovalFlow.sequence_order).first()
                    if flow:
                        return flow, ExpenseStatus.IN_PROGRESS
        
        elif rule.rule_type == 'specific':
            # Always route to specific approver
            if rule.specific_approver_id:
                flow = ApprovalFlow.query.filter_by(
                    company_id=company_id,
                    approver_id=rule.specific_approver_id
                ).first()
                if flow:
                    return flow, ExpenseStatus.IN_PROGRESS
        
        elif rule.rule_type == 'hybrid':
            # Implement hybrid logic based on rule.hybrid_logic
            # For now, fall back to manager approval
            if user.manager_id:
                flow = ApprovalFlow.query.filter_by(
                    company_id=company_id,
                    approver_id=user.manager_id
                ).first()
                if flow:
                    return flow, ExpenseStatus.IN_PROGRESS
    
    # Default: no specific flow matched, use manager if available
    if user.manager_id:
        # Create or get a simple manager approval flow
        flow = ApprovalFlow.query.filter_by(
            company_id=company_id,
            step_number=1,
            approver_id=user.manager_id
        ).first()
        
        if not flow:
            flow = ApprovalFlow(
                company_id=company_id,
                step_number=1,
                approver_id=user.manager_id,
                sequence_order=1
            )
            db.session.add(flow)
            db.session.flush()
        
        return flow, ExpenseStatus.IN_PROGRESS
    
    return None, ExpenseStatus.PENDING