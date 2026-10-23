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

ALLOWED_HOSTS = allowed_hosts_from(os.environ, required=True)

DATABASES = {'default': database_from(os.environ)}


# --- HTTPS only -------------------------------------------------------------
# https://docs.djangoproject.com/en/5.2/topics/security/#ssl-https

# The host (Render) ends HTTPS and forwards plain HTTP to Django, adding
# X-Forwarded-Proto: https. This tells Django to trust that header. Without it,
# Django sees every request as insecure and SECURE_SSL_REDIRECT loops forever.
# Only safe because the host sets the header itself; never set this when
# clients can reach Django directly.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Send any http:// request to https://.
SECURE_SSL_REDIRECT = True

# Except the health checks (#27): the host calls them over plain HTTP from
# inside its network, and a redirect instead of a 200 would mark the app
# unhealthy. Django matches these against the path without its leading slash.
SECURE_REDIRECT_EXEMPT = [r'^health/$', r'^ready/$']

# Only send the session and CSRF cookies over HTTPS, so they can't be read
# off an unencrypted connection.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS: browsers use HTTPS only for this site, for this many seconds.
SECURE_HSTS_SECONDS = hsts_seconds_from(os.environ)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# HSTS preload (security.W021) is left off on purpose: the browser preload list
# is very hard to leave, requires a one-year max-age, and does not accept a
# subdomain of a shared host such as *.onrender.com.
SILENCED_SYSTEM_CHECKS = ['security.W021']
