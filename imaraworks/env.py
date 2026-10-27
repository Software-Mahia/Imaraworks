"""
Read deployment settings from environment variables (issues #21 and #24).

The rules live here, not inline in the settings modules, so they can be
unit-tested with a plain dict instead of reloading Django's settings.

Everything fails safe: if a variable is forgotten on the deployed demo, the
app refuses to start. It never falls back to a development value in production.
"""

from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

# Used only by the dev settings (a developer's machine, the test runner, CI).
# It is not a secret: the prod settings refuse to start unless DJANGO_SECRET_KEY is set.
DEV_SECRET_KEY = 'django-insecure-dev-only-not-for-the-deployed-demo'

DEFAULT_ALLOWED_HOSTS = 'localhost,127.0.0.1'

# One hour. Browsers remember HSTS for this long, so if HTTPS breaks, visitors
# are locked out only briefly. Raise it (e.g. to a year, 31536000) once the
# demo has run over HTTPS without problems.
DEFAULT_HSTS_SECONDS = 3600


def secret_key_from(environ, *, allow_dev_key):
    """Use DJANGO_SECRET_KEY if set; else the dev key if allowed; otherwise refuse to start."""
    key = environ.get('DJANGO_SECRET_KEY', '').strip()
    if key:
        return key
    if allow_dev_key:
        return DEV_SECRET_KEY
    raise ImproperlyConfigured(
        'DJANGO_SECRET_KEY is not set. For the deployed demo, set it to a new random key.'
    )


def allowed_hosts_from(environ, *, required=False):
    """Comma-separated DJANGO_ALLOWED_HOSTS.

    Optional in dev, where it defaults to the local machine only. Required in
    prod, which must be told the host it serves.
    """
    default = '' if required else DEFAULT_ALLOWED_HOSTS
    raw = environ.get('DJANGO_ALLOWED_HOSTS', default)
    hosts = [host.strip() for host in raw.split(',') if host.strip()]
    if required and not hosts:
        raise ImproperlyConfigured(
            'DJANGO_ALLOWED_HOSTS is not set. Set it to the demo\'s host name, '
            'e.g. imaraworks.onrender.com.'
        )
    return hosts


def database_from(environ):
    """The database from DATABASE_URL, e.g. postgres://user:password@host:5432/name.

    conn_max_age keeps each connection open for up to 10 minutes, instead of
    opening a new one for every request.
    """
    url = environ.get('DATABASE_URL', '').strip()
    if not url:
        raise ImproperlyConfigured(
            'DATABASE_URL is not set. Set it to the production database\'s connection URL.'
        )
    return dj_database_url.parse(url, conn_max_age=600)


def hsts_seconds_from(environ):
    """DJANGO_HSTS_SECONDS as a whole number of seconds, defaulting to one hour."""
    raw = environ.get('DJANGO_HSTS_SECONDS')
    if raw is None:
        return DEFAULT_HSTS_SECONDS
    if not raw.strip().isdigit():
        raise ImproperlyConfigured(
            f'DJANGO_HSTS_SECONDS must be a whole number of seconds, not {raw!r}.'
        )
    return int(raw)


def refuse_dev_settings_on_server(environ):
    """Stop the dev settings from running on the server.

    DATABASE_URL is only set on the server. If it is there while the dev
    settings are loaded (e.g. `manage.py migrate` run without
    DJANGO_SETTINGS_MODULE), carrying on would use a local SQLite file with
    DEBUG on, instead of the real database.
    """
    if environ.get('DATABASE_URL', '').strip():
        raise ImproperlyConfigured(
            'DATABASE_URL is set, so this looks like the server, but the dev settings '
            'are loaded. Set DJANGO_SETTINGS_MODULE=imaraworks.settings.prod.'
        )


def database_path_from(environ, *, base_dir):
    """Path to the local SQLite database file.

    Defaults to ``<project>/db.sqlite3`` so ordinary local runs are unchanged.
    Containers set DJANGO_DB_PATH to a file on a mounted volume (see
    docker-compose.yml), so the database survives a restart. SQLite is a local
    development choice; the deployed demo uses managed Postgres (DATABASE_URL).
    """
    raw = environ.get('DJANGO_DB_PATH', '').strip()
    return Path(raw) if raw else Path(base_dir) / 'db.sqlite3'
