from __future__ import annotations

import os
import sys
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from flask import Blueprint

from app import create_app
from expenses.forms import BudgetDeleteForm, BudgetForm, CategoryDeleteForm, CategoryForm, ExpenseForm


def fake_field(render_html: str):
    class _Field:
        errors: list[str] = []

        def __call__(self, **kwargs):
            return render_html

    return _Field()


def main() -> None:
    app = create_app()

    # Provide stub routes used in shared templates that aren't part of this smoke harness
    main_bp = Blueprint("main", __name__)

    @main_bp.route("/")
    def index():  # pragma: no cover - test harness helper
        return ""

    @main_bp.route("/dashboard")
    def dashboard():  # pragma: no cover - test harness helper
        return ""

    manager_bp = Blueprint("manager", __name__)

    @manager_bp.route("/manager/pending")
    def pending_approvals():  # pragma: no cover - test harness helper
        return ""

    @manager_bp.route("/manager/team")
    def team_expenses():  # pragma: no cover - test harness helper
        return ""

    app.register_blueprint(main_bp)
    app.register_blueprint(manager_bp)
    if "auth.profile" not in app.view_functions:
        app.add_url_rule("/profile", endpoint="auth.profile", view_func=lambda: "")
    if "auth.settings" not in app.view_functions:
        app.add_url_rule("/settings", endpoint="auth.settings", view_func=lambda: "")

    with app.app_context(), app.test_request_context('/'):
        sample_expense = SimpleNamespace(
            title="Cloud subscription",
            description="Monthly SaaS charge",
            category=SimpleNamespace(name="Software"),
            amount=Decimal("129.00"),
            currency="USD",
            status=SimpleNamespace(name="PENDING"),
            spent_at=date(2025, 9, 15),
            submitted_at=datetime(2025, 9, 16, 10, 30),
        )
        employee_pagination = SimpleNamespace(
            page=1,
            per_page=10,
            total=1,
            pages=1,
            has_prev=False,
            has_next=False,
            prev_page=None,
            next_page=None,
        )
        html_employee = app.jinja_env.get_template("employee/expenses.html").render(
            stats={"pending": 2, "approved": 5, "rejected": 1},
            expenses=[sample_expense],
            pagination=employee_pagination,
            filters={"status": "", "search": ""},
            current_user=SimpleNamespace(is_authenticated=True, role="employee", first_name="Alicia"),
        )
        print("employee/expenses.html rendered", len(html_employee))

        expense_form = ExpenseForm(meta={"csrf": False})
        expense_form.title.data = "Test expense"
        expense_form.description.data = "Test description"
        expense_form.amount.data = Decimal("100.00")
        expense_form.currency.choices = [("USD", "USD")]
        expense_form.currency.data = "USD"
        expense_form.category.choices = [(1, "General")]
        expense_form.category.data = "1"
        expense_form.spent_at.data = date.today()
        html_submit_expense = app.jinja_env.get_template("employee/submit_expense.html").render(
            form=expense_form,
            current_user=SimpleNamespace(is_authenticated=True, role="employee", first_name="Alicia"),
        )
        print("employee/submit_expense.html rendered", len(html_submit_expense))

        manager_expense = SimpleNamespace(
            title="Conference Travel",
            description="Flights and hotel",
            category=SimpleNamespace(name="Travel"),
            amount=Decimal("1540.00"),
            currency="USD",
            status=SimpleNamespace(name="PENDING"),
            spent_at=date(2025, 9, 5),
            submitted_at=datetime(2025, 9, 6, 14, 45),
            submitter=SimpleNamespace(name="Alicia Carter", email="alicia@example.com"),
            company=SimpleNamespace(name="ExpensoX", country="USA"),
            approver=None,
            decided_at=None,
            manager_notes=None,
            id=42,
        )
        manager_pagination = SimpleNamespace(
            page=1,
            per_page=10,
            total=1,
            pages=1,
            has_prev=False,
            has_next=False,
            prev_page=None,
            next_page=None,
        )
        html_manager_list = app.jinja_env.get_template("manager/pending_approvals.html").render(
            stats={"total": 1, "today": 0, "overdue": 0, "total_amount": 1540.00},
            expenses=[manager_expense],
            pagination=manager_pagination,
            filters={"status": "PENDING", "search": ""},
            current_user=SimpleNamespace(is_authenticated=True, role="manager", first_name="Morgan"),
        )
        print("manager/pending_approvals.html rendered", len(html_manager_list))

        decision_form = SimpleNamespace(
            hidden_tag=lambda: "",
            decision=fake_field('<select name="decision"></select>'),
            notes=fake_field('<textarea name="notes"></textarea>'),
            submit=fake_field('<button type="submit">Submit</button>'),
        )
        html_manager_detail = app.jinja_env.get_template("manager/approval_detail.html").render(
            expense=manager_expense,
            form=decision_form,
            current_user=SimpleNamespace(is_authenticated=True, role="manager", first_name="Morgan"),
        )
        print("manager/approval_detail.html rendered", len(html_manager_detail))

        html_auth_public = app.jinja_env.get_template("auth/index.html").render()
        print("auth/index.html (marketing) rendered", len(html_auth_public))

        employee_dashboard_context = SimpleNamespace(
            first_name="Alicia",
            role="Employee",
            company=SimpleNamespace(name="ExpensoX", currency="USD"),
            currency="USD",
            employee=SimpleNamespace(
                total_count=8,
                status_counts={"pending": 2, "approved": 5, "rejected": 1},
                total_amount=Decimal("2389.00"),
                last_submitted=sample_expense,
                recent_expenses=[sample_expense],
            ),
            manager=None,
        )
        html_auth_dashboard_employee = app.jinja_env.get_template("auth/index.html").render(
            dashboard=True,
            dashboard_context=employee_dashboard_context,
            user=SimpleNamespace(name="Alicia Carter", role="Employee"),
        )
        print("auth/index.html (employee dashboard) rendered", len(html_auth_dashboard_employee))

        manager_dashboard_context = SimpleNamespace(
            first_name="Morgan",
            role="Manager",
            company=SimpleNamespace(name="ExpensoX", currency="USD"),
            currency="USD",
            employee=None,
            manager=SimpleNamespace(
                pending_total=1,
                pending_amount=Decimal("1540.00"),
                status_counts={"pending": 1, "approved": 4, "rejected": 0},
                recent_expenses=[manager_expense],
                team_size=5,
                team_members=[
                    SimpleNamespace(name="Alicia Carter"),
                    SimpleNamespace(name="Jordan Blake"),
                    SimpleNamespace(name="Priya Singh"),
                ],
                monthly_total=Decimal("3120.50"),
                avg_processing_days=2.4,
            ),
        )
        html_auth_dashboard_manager = app.jinja_env.get_template("auth/index.html").render(
            dashboard=True,
            dashboard_context=manager_dashboard_context,
            user=SimpleNamespace(name="Morgan Lane", role="Manager"),
        )
        print("auth/index.html (manager dashboard) rendered", len(html_auth_dashboard_manager))

        category_form = CategoryForm(meta={"csrf": False})
        category_form.name.data = "Travel"
        category_form.description.data = "Flights, hotels, mileage"
        delete_form = CategoryDeleteForm(meta={"csrf": False})
        sample_category = SimpleNamespace(
            id=1,
            name="Travel",
            description="Flights, hotels, mileage",
            created_at=datetime(2025, 1, 5),
            updated_at=datetime(2025, 1, 10),
        )
        category_user = SimpleNamespace(is_authenticated=True, role="manager", first_name="Alex")
        html_categories = app.jinja_env.get_template("admin/categories.html").render(
            form=category_form,
            delete_form=delete_form,
            categories=[sample_category],
            expense_counts={1: 3},
            search_query="",
            current_user=category_user,
        )
        print("admin/categories.html rendered", len(html_categories))

        edit_form = CategoryForm(meta={"csrf": False})
        edit_form.name.data = sample_category.name
        edit_form.description.data = sample_category.description
        edit_form.submit.label.text = "Update category"
        html_edit_category = app.jinja_env.get_template("admin/edit_category.html").render(
            form=edit_form,
            category=sample_category,
            current_user=category_user,
        )
        print("admin/edit_category.html rendered", len(html_edit_category))

        budget_form = BudgetForm(meta={"csrf": False})
        budget_form.category.choices = [(sample_category.id, sample_category.name)]
        budget_form.category.data = sample_category.id
        budget_form.amount.data = Decimal("2500.00")
        budget_form.period_start.data = date(2025, 10, 1)
        budget_form.period_end.data = date(2025, 10, 31)
        budget_form.description.data = "Q4 travel budget"
        budget_delete_form = BudgetDeleteForm(meta={"csrf": False})
        sample_budget = SimpleNamespace(
            id=10,
            category=sample_category,
            amount=Decimal("2500.00"),
            currency="USD",
            period_start=date(2025, 10, 1),
            period_end=date(2025, 10, 31),
            description="Q4 travel budget",
            created_at=datetime(2025, 9, 1, 9, 30),
            updated_at=datetime(2025, 9, 15, 12, 0),
        )
        budget_rows = [
            {
                "budget": sample_budget,
                "spent": Decimal("1800.00"),
                "remaining": Decimal("700.00"),
                "usage_percent": 72.0,
                "is_over_limit": False,
            }
        ]
        html_budgets = app.jinja_env.get_template("admin/budgets.html").render(
            form=budget_form,
            delete_form=budget_delete_form,
            budgets=budget_rows,
            categories=[sample_category],
            company_currency="USD",
            search_query="",
            current_user=category_user,
        )
        print("admin/budgets.html rendered", len(html_budgets))

        edit_budget_form = BudgetForm(meta={"csrf": False})
        edit_budget_form.category.choices = budget_form.category.choices
        edit_budget_form.category.data = sample_category.id
        edit_budget_form.amount.data = Decimal("2500.00")
        edit_budget_form.period_start.data = sample_budget.period_start
        edit_budget_form.period_end.data = sample_budget.period_end
        edit_budget_form.description.data = sample_budget.description
        edit_budget_form.submit.label.text = "Update budget"
        html_edit_budget = app.jinja_env.get_template("admin/edit_budget.html").render(
            form=edit_budget_form,
            budget=sample_budget,
            categories=[sample_category],
            company_currency="USD",
            current_user=category_user,
        )
        print("admin/edit_budget.html rendered", len(html_edit_budget))


if __name__ == "__main__":
    main()
