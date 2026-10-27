# System architecture

![System architecture](images/system_architecture.png)

## What the system is

ImaraWorks is a vendor payment and approval system (KamiLimu ICT Track case study). Employees raise payment requests to vendors, managers and finance officers approve them by value, finance pays through a payment gateway, and every state change is audit-logged. Reporting summarises the money.

## Stack

Django 5.2 + Django REST Framework + SimpleJWT (auth), WhiteNoise (static files with DEBUG off), SQLite locally / Postgres on the server (`DATABASE_URL`), server-rendered frontend pages with vanilla JS, GitHub Actions CI, Render Blueprint for the deployed demo, Docker/Compose for local development, Python 3.14.

## Apps

| App | Owns |
|---|---|
| `apps.accounts` | Users, `Profile` (role), `/api/health/`, `/api/auth/me/` |
| `apps.vendors` | Vendors, `GET /api/vendors/` |
| `apps.payment_requests` | `PaymentRequest` + `Project` models, create/list/detail, visibility rules, `seed_users` |
| `apps.approvals` | Approval rules (`logic.py`), workflow service (`services.py`), queue, submit/approve/reject/amount |
| `apps.payments` | Gateway adapter + mock provider, transaction lifecycle, pay endpoints |
| `apps.audit` | Append-only audit log: per-request history + ADMIN audit view |
| `apps.reporting` | Summary totals with role-scoped filters |
| `frontend` | HTML pages (`/login/`, `/employee/`, `/manager/`, `/finance/`) + JS (JWT auth, role guard) |
| `imaraworks` | Settings split (`base` / `dev` / `prod`), env rules (`env.py`) |

Views only translate HTTP ⇄ a `services.py` call; every business rule lives in a service or `logic.py`.

## Request lifecycle

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> PENDING_APPROVAL: submit (requester)
    PENDING_APPROVAL --> APPROVED: every required level approves
    PENDING_APPROVAL --> REJECTED: reject (reason required)
    APPROVED --> PROCESSING: finance pays
    PROCESSING --> PAID: gateway succeeds
    PROCESSING --> FAILED: gateway declines or errors
    FAILED --> PROCESSING: retry
    PAID --> [*]
    REJECTED --> [*]
```

- **Thresholds**: ≤ KES 50,000 → one `manager` approval; > 50,000 → `manager` **and** `finance`, in either order.
- **Separation of duties**: nobody approves or pays a request they created.
- **Amount change** while `PENDING_APPROVAL`/`APPROVED`: every approval stops counting, status returns to `PENDING_APPROVAL`, levels are recalculated.
- Concurrent approval at the same level is answered `409`, not 500.

## Settings and configuration

`manage.py` uses `dev.py` by default (DEBUG on, SQLite, zero setup — tests and CI too). `wsgi.py`/`asgi.py` use `prod.py` (DEBUG always off). Everything shared lives in `base.py`. Secrets come from environment variables only; **prod refuses to start if one is missing, and dev refuses to start if `DATABASE_URL` is set** (it means the server was meant to run prod).

| Variable | Local development | Deployed demo |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | not needed | **required**: `imaraworks.settings.prod`, so `manage.py` commands on the server use prod too |
| `DJANGO_SECRET_KEY` | not needed (dev key) | **required**: a new random key, kept out of git |
| `DJANGO_ALLOWED_HOSTS` | not needed (defaults to `localhost,127.0.0.1`) | **required**: the domain, comma-separated |
| `DATABASE_URL` | must not be set | **required**: `postgres://user:password@host:5432/name` |
| `DJANGO_HSTS_SECONDS` | unused | optional, defaults to `3600` (raise once HTTPS is proven) |
| `SEED_USER_PASSWORD` | not needed (dev password while DEBUG) | required to run `seed_users` on the server |

## Security posture

- **Auth**: JWT access tokens (~5 minutes) + refresh tokens; every endpoint enforces roles server-side (`403` for the wrong role, `404` where visibility hides the object).
- **Production**: `DEBUG` off, HTTPS redirect, HSTS, secure session/CSRF cookies, `X-Forwarded-Proto` aware (Render proxy), WhiteNoise for static files.
- **Data protection**: admins deliberately see **no** payment data — they get the redacted audit log instead; amounts are decimals (never floats); the audit log is append-only (entries are never edited or deleted).
- **Deployment safety is tested in CI**: `manage.py check --deploy --fail-level WARNING` runs against `prod.py` with stand-in values on every push/PR.

## Health checks

The host uses two unauthenticated endpoints (issue #27), both exempt from the HTTPS redirect in production:

- `GET /health/` — liveness: the process is up and can answer. No database access.
- `GET /ready/` — readiness: runs `SELECT 1` and answers `503` when the database is unreachable.

`GET /api/health/` is an older alias of `/health/`.

## Deployment and Docker

- **Render (deployed demo)**: `render.yaml` creates the Postgres database and the web service together, wires `DATABASE_URL`, runs `collectstatic` at build time, migrates in `preDeployCommand`, and health-checks `/health/`.
- **Docker (local development)**: `Dockerfile` builds a non-root image; `entrypoint.sh` applies migrations on start (and seeds demo users when `SEED_USERS=1`); `docker-compose.yml` runs the dev settings with SQLite on the `sqlite_data` volume. Variables are documented in `.env.example`.

## Storage

- Dev/test/CI: `db.sqlite3` file (ignored by git).
- Server: Postgres via `dj-database-url`, connections kept open up to 10 minutes (`conn_max_age=600`).

## Continuous integration

`.github/workflows/ci.yml` runs on pushes to `main` and on every PR: `makemigrations --check --dry-run` (model changes without a migration fail), `manage.py test`, then the deploy check above.

## Documentation map

- [API.md](API.md) — every endpoint, approval workflow, payments, reports, conventions, errors, test users (including `/admin/` and `/api-auth/` usage)
- [MOCK_PROVIDER.md](MOCK_PROVIDER.md) — payment gateway design and the mock provider
- [RUNNING_IT_ON_YOUR_MACHINE.md](RUNNING_IT_ON_YOUR_MACHINE.md) — local setup, Docker, Django admin/browsable API, inspecting headers and bodies
- [PART_B_NOTES.md](PART_B_NOTES.md) — Part B presentation notes
