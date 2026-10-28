[![Coverage Status](https://coveralls.io/repos/github/imaraworks-team/Imaraworks/badge.svg?branch=main)](https://coveralls.io/github/imaraworks-team/Imaraworks)

# ImaraWorks Vendor Payment & Approval System

A Django REST API for submitting, approving, paying and reporting vendor payment requests. KamiLimu ICT Track case study.

![System architecture](docs/images/system_architecture.png)

## Quick start

```
python -m venv venv
venv\Scripts\Activate.ps1        # Windows; macOS/Linux: source venv/bin/activate
pip install -r requirements.txt  # re-run after every pull that changes requirements.txt
python manage.py migrate
python manage.py seed_users
python manage.py runserver
```

Tests: `python manage.py test`.

## Live demo

- App: https://imaraworks-dwtq.onrender.com
- Health check: https://imaraworks-dwtq.onrender.com/health/

The demo runs on Render's free plan, so the first request after a quiet period can take about a minute.
The free database expires on 2026-11-27; see [Database, backups and restore](docs/BACKUPS.md).

## Test accounts (local password: `password123`)

| Username | Role |
|---|---|
| alice, brian | Employee |
| carol, david | Manager |
| faith, fiona | Finance Officer |
| grace | Administrator |

## Contributors

| Name | GitHub | Area |
|---|---|---|
| Tamira Atieno | [@TamiraAtieno1](https://github.com/TamiraAtieno1) | Accounts, vendors and payment requests |
| Joylynn Wamjiru | [@JoylynnWamjiru](https://github.com/JoylynnWamjiru) | Approvals, audit, reporting, settings and CI |
| Lewis Gitau | [@codingwithgitau](https://github.com/codingwithgitau) | Frontend |
| Isaac Mwangi | [@B1t-Master](https://github.com/B1t-Master) | Payments (mock provider) and DevOps |

## Documentation

- [docs/API.md](docs/API.md) — endpoints, approval workflow, payments, reports, errors, conventions (and how to use `/admin/`, `/api-auth/`, headers/body)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system architecture, settings, security, health checks, deployment/Docker, CI
- [docs/RUNNING_IT_ON_YOUR_MACHINE.md](docs/RUNNING_IT_ON_YOUR_MACHINE.md) — local setup, Docker, admin/browsable API, headers and body inspection
- [docs/FRONTEND.md](docs/FRONTEND.md) — frontend notes: known limitations, how AI was used, observability
- [Database, backups and restore](docs/BACKUPS.md)

## How AI was used

AI assistants (Claude) were used for design research, first drafts and help with code review. The rule: AI output is a draft. It is run and tested locally, checked against docs/API.md and real API responses, and reviewed by a teammate before it is merged. The frontend lane's details, including examples of AI output that was corrected in review, are in [docs/FRONTEND.md](docs/FRONTEND.md).