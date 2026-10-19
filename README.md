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

### Settings

Settings are split by environment (issue #24), and secrets come from
environment variables, never from the code (issue #21):

- `imaraworks/settings/base.py`: everything shared.
- `imaraworks/settings/dev.py`: used by `manage.py` by default. DEBUG on, SQLite, no setup needed.
  Tests and CI use it too.
- `imaraworks/settings/prod.py`: used by `wsgi.py`/`asgi.py`. DEBUG always off, and it refuses to
  start unless every variable below is set.

| Variable | Local development | Deployed demo |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | not needed | **required**: `imaraworks.settings.prod`, so `manage.py` commands on the server use prod too |
| `DJANGO_SECRET_KEY` | not needed | **required**: a new random key, kept out of git |
| `DJANGO_ALLOWED_HOSTS` | not needed (defaults to `localhost,127.0.0.1`) | **required**: the demo's domain, comma-separated |
| `DATABASE_URL` | don't set it | **required**: the database URL, e.g. `postgres://user:password@host:5432/name` |

Generate a key with
`python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`.

If `DATABASE_URL` is set while the dev settings are loaded, the app refuses to start: that means
it is running on the server without `DJANGO_SETTINGS_MODULE`, and would otherwise use a local
SQLite file instead of the real database.

## Test accounts (local password: `password123`)

`password123` is for local development only. With the prod settings (DEBUG off),
`seed_users` refuses to run unless `SEED_USER_PASSWORD` is set, so the deployed
demo's accounts get a password that is not in this repo (issue #21).

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