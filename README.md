# ImaraWorks Vendor Payment & Approval System

A Django REST API for submitting, approving and tracking vendor payment requests.
KamiLimu ICT Track case study.

## Setup

```
python -m venv venv
venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_users
python manage.py runserver
```

## Test accounts (password: `password123`)

| Username | Role |
|---|---|
| alice, brian | Employee |
| carol, david | Manager |
| faith | Finance Officer |
| grace | Administrator |

## Project structure

- `apps/accounts` - roles, login, `/api/auth/me/`
- `apps/vendors` - vendors
- `apps/payment_requests` - payment requests, projects, validation
- `apps/approvals`, `apps/payments`, `apps/audit`, `apps/reporting` - in progress
- `frontend` - templates and static files
- `tests` - automated tests

## Running tests

```
python manage.py test
```

## Team

| Area | Owner |
|---|---|
| Accounts, vendors, payment requests | A |
| Approvals | B |
| Payments | C |
| Frontend | D |