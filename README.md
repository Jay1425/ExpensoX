<h1 align="center">ExpensoX Backend — Phase 1</h1>

An opinionated Flask project scaffold for ExpensoX, an expense management and multi-level approval workflow platform. This repository delivers the backend skeleton, service stubs, and modular structure that future phases will extend with full business logic, OCR, background jobs, and a Tailwind-powered UI.

---
demo  video:- https://drive.google.com/file/d/1KdqvHJWlKSqZF1Uvif2vCOZL7Zp5MzMK/view?usp=sharing
## 🌐 Tech Stack

- **Flask 3** with Blueprints and application factory pattern
- **SQLAlchemy** ORM + **Flask-Migrate** migrations (SQLite for development)
- **Flask-Login** for user sessions
- **Flask-WTF** (forms & CSRF protection)
- **Requests** for REST integrations (currency + country APIs)
- Placeholder hooks for OCR (Tesseract/EasyOCR) and background tasks (Celery + Redis)

---

## ✨ Latest Enhancements (October 2025)

- Employee and manager expense views now support fast pagination, status filtering, and search.
- Managers trigger notification emails when approving or rejecting expenses, keeping submitters informed.
- New category management workspace for admins/managers with create, edit, and delete flows.
- Budget controls let teams cap category spend, visualize usage, and monitor overruns from a single dashboard.

---

## 🏗️ Project Structure

```
ExpensoX/
├── run.py
├── config.py
├── requirements.txt
├── .env.example
├── app/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── company.py
│   │   ├── user.py
│   │   ├── expense.py
│   │   ├── approval.py
│   │   └── audit.py
│   ├── auth/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── admin/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── employee/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── manager/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── currency_service.py
│   │   ├── ocr_service.py
│   │   └── approval_engine.py
│   ├── utils/
│   │   ├── __init__.py
│   │   └── helpers.py
│   ├── templates/
│   └── static/
└── migrations/
```

---

## ⚙️ Quick Start

1. **Clone & create environment**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. **Configure environment variables**

```powershell
Copy-Item .env.example .env
```

Update `.env` with secure values (`SECRET_KEY`, optional `DATABASE_URL`, etc.).

3. **Initialize database**

```powershell
flask db init
flask db migrate -m "Initial tables"
flask db upgrade
```

4. **Run the dev server**

```powershell
flask run
```

The API will be available at `http://127.0.0.1:5000/`.

---

## � Implemented Endpoints (Phase 1)

| Module    | Endpoint                              | Description |
|-----------|----------------------------------------|-------------|
| Auth      | `POST /auth/signup`                    | First signup bootstraps company + admin. Subsequent users join existing companies. |
|           | `POST /auth/login`                     | Session-based login with Flask-Login. |
|           | `GET /auth/logout`                     | Logout the active session. |
| Employee  | `GET /employee/expenses`               | List current employee's submitted expenses. |
|           | `POST /employee/expenses`              | Submit a new expense; currency conversion and approval generation are stubbed. |
| Manager   | `GET /manager/pending`                 | View pending approvals assigned to the manager. |
|           | `POST /manager/approve/<expense_id>`   | Approve a pending expense (placeholder workflow). |
|           | `POST /manager/reject/<expense_id>`    | Reject a pending expense. |
| Admin     | `GET /admin/users`                     | List users for the admin's company. |
|           | `POST /admin/users`                    | Create employee or manager accounts. |
|           | `POST /admin/approval-flow`            | Create/update approval flows (placeholder). |
|           | `POST /admin/approval-rule`            | Create approval rules with stub evaluation response. |

All responses currently return JSON payloads to support rapid frontend prototyping.

---

## 🔮 Next Phases

- Wire up real OCR processing and receipt storage.
- Enforce multi-step approval sequencing with rule evaluation.
- Introduce Celery/Redis for asynchronous tasks (e.g., OCR, notifications).
- Add Tailwind + HTMX frontend, dashboards, and audit views.
- Harden validation, logging, and error handling; add tests.

---

## 🤝 Contributing

1. Fork & branch from `main`.
2. Keep PRs focused per module or feature.
3. Include tests where practical and update documentation as functionality evolves.

---

Made with care for the ExpensoX platform.
