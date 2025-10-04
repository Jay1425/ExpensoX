from __future__ import annotations

import os
import sys
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from flask import Blueprint

from app import create_app


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
        html_employee = app.jinja_env.get_template("employee/expenses.html").render(
            stats={"pending": 2, "approved": 5, "rejected": 1},
            expenses=[sample_expense],
            current_user=SimpleNamespace(is_authenticated=True, role="employee", first_name="Alicia"),
        )
        print("employee/expenses.html rendered", len(html_employee))

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
        html_manager_list = app.jinja_env.get_template("manager/pending_approvals.html").render(
            stats={"total": 1, "today": 0, "overdue": 0, "total_amount": 1540.00},
            expenses=[manager_expense],
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


if __name__ == "__main__":
    main()
