# Running it on your machine

## Quick start (local, no Docker)
```bash
python -m venv venv
# Windows: venv\Scripts\Activate.ps1
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_users
python manage.py runserver
```
Tests: `python manage.py test`. Password for all seeded users: `password123` (local dev settings).

## Docker (recommended for a clean, reproducible run)
```bash
cp .env.example .env  # adjust if needed
docker compose up --build
```
- The entrypoint runs migrations on every start and seeds demo users when `SEED_USERS=1` (set in `docker-compose.yml`).
- SQLite is stored on the `sqlite_data` volume at `DJANGO_DB_PATH` (default `/app/data/db.sqlite3`).
- Health: `GET http://localhost:8000/health/` and `GET http://localhost:8000/ready/` (readiness checks the DB).

See `.env.example` for environment variables.

## Django admin and browsing the APIs
- Django admin: [http://localhost:8000/admin/](http://localhost:8000/admin/) — manage users/profiles, vendors/projects and inspect records.
- DRF browsable API: [http://localhost:8000/api-auth/login/](http://localhost:8000/api-auth/login/) — log in with a test account to use the browsable forms. You can also call JSON endpoints directly.
- JSON endpoints (e.g. `POST /api/auth/login/`, `GET /api/vendors/`, `GET /api/payment-requests/`) expect `Authorization: Bearer <access token>` for protected routes. Get tokens from `POST /api/auth/login/`. To inspect headers/body, use your browser DevTools (Network) or `curl -v ...`.

## Test accounts
alice, brian (EMPLOYEE); carol, david (MANAGER); faith, fiona (FINANCE); grace (ADMIN). Password: `password123`.
