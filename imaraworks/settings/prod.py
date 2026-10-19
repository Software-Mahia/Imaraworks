"""Settings for the deployed demo (issue #24).

wsgi.py and asgi.py use this by default, and the server can also select it
with DJANGO_SETTINGS_MODULE=imaraworks.settings.prod. Everything shared lives
in base.py.
"""

from .base import *  # noqa: F401,F403
