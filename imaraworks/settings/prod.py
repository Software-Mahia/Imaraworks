"""Settings for the deployed demo (issue #24).

wsgi.py and asgi.py use this by default. On the server, also set
DJANGO_SETTINGS_MODULE=imaraworks.settings.prod, so that manage.py commands
(migrate, createsuperuser) use it too.

Strict by default: DEBUG is always off, and the app refuses to start unless
DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS and DATABASE_URL are all set. Nothing
falls back to a development value. Everything shared lives in base.py.
"""

import os

from imaraworks.env import allowed_hosts_from, database_from, secret_key_from

from .base import *  # noqa: F401,F403

DEBUG = False

SECRET_KEY = secret_key_from(os.environ, allow_dev_key=False)

ALLOWED_HOSTS = allowed_hosts_from(os.environ, required=True)

DATABASES = {'default': database_from(os.environ)}
