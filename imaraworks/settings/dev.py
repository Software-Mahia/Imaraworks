"""Settings for a developer's machine, the test runner and CI (issue #24).

manage.py uses this by default. It needs no setup: DEBUG is on, the database
is a local SQLite file, and a dev-only key is used unless DJANGO_SECRET_KEY is
set. Everything shared lives in base.py.
"""

import os

from imaraworks.env import allowed_hosts_from, refuse_dev_settings_on_server, secret_key_from

from .base import *  # noqa: F401,F403
from .base import BASE_DIR

refuse_dev_settings_on_server(os.environ)

DEBUG = True

SECRET_KEY = secret_key_from(os.environ, allow_dev_key=True)

ALLOWED_HOSTS = allowed_hosts_from(os.environ)

# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
