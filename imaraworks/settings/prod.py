"""Settings for the deployed demo (issue #24).

wsgi.py and asgi.py use this by default. On the server, also set
DJANGO_SETTINGS_MODULE=imaraworks.settings.prod, so that manage.py commands
(migrate, createsuperuser) use it too.

Strict by default: DEBUG is always off, and the app refuses to start unless
DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS and DATABASE_URL are all set. Nothing
falls back to a development value. Everything shared lives in base.py.
"""

import os

from imaraworks.env import allowed_hosts_from, database_from, hsts_seconds_from, secret_key_from

from .base import *  # noqa: F401,F403

DEBUG = False

SECRET_KEY = secret_key_from(os.environ, allow_dev_key=False)

# Build ALLOWED_HOSTS from environment, then add Render's external hostname if available.
# Render automatically sets RENDER_EXTERNAL_HOSTNAME - appending it means the demo
# works without hardcoding the hostname in render.yaml or CI secrets.
_ALLOWED_HOSTS = allowed_hosts_from(os.environ, required=True)
_render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if _render_hostname and _render_hostname not in _ALLOWED_HOSTS:
    _ALLOWED_HOSTS.append(_render_hostname)

ALLOWED_HOSTS = _ALLOWED_HOSTS

DATABASES = {'default': database_from(os.environ)}
