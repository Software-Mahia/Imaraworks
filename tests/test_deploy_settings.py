"""
Issue #21: deployment settings come from environment variables and fail safe.

The rules are tested as pure functions on a plain dict, so no test has to
reload Django's settings or touch the real environment.
"""

import importlib
import os
import sys
from unittest import mock

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from imaraworks.env import (
    DEV_SECRET_KEY,
    allowed_hosts_from,
    database_from,
    refuse_dev_settings_on_server,
    secret_key_from,
)


class SecretKeyFromTests(SimpleTestCase):
    def test_uses_env_key_when_set(self):
        key = secret_key_from({'DJANGO_SECRET_KEY': 'from-env'}, allow_dev_key=False)
        self.assertEqual(key, 'from-env')

    def test_env_key_wins_even_in_dev(self):
        key = secret_key_from({'DJANGO_SECRET_KEY': 'from-env'}, allow_dev_key=True)
        self.assertEqual(key, 'from-env')

    def test_dev_key_when_allowed(self):
        self.assertEqual(secret_key_from({}, allow_dev_key=True), DEV_SECRET_KEY)

    def test_refuses_to_start_without_key_in_production(self):
        with self.assertRaises(ImproperlyConfigured):
            secret_key_from({}, allow_dev_key=False)

    def test_blank_key_counts_as_unset(self):
        with self.assertRaises(ImproperlyConfigured):
            secret_key_from({'DJANGO_SECRET_KEY': '   '}, allow_dev_key=False)


class AllowedHostsFromTests(SimpleTestCase):
    def test_defaults_to_local_machine_only(self):
        self.assertEqual(allowed_hosts_from({}), ['localhost', '127.0.0.1'])

    def test_reads_comma_separated_list(self):
        hosts = allowed_hosts_from({'DJANGO_ALLOWED_HOSTS': 'demo.example.com, .onrender.com'})
        self.assertEqual(hosts, ['demo.example.com', '.onrender.com'])

    def test_ignores_empty_entries(self):
        self.assertEqual(allowed_hosts_from({'DJANGO_ALLOWED_HOSTS': 'a.com,,'}), ['a.com'])


class AllowedHostsRequiredTests(SimpleTestCase):
    """Prod has no default: it must be told which host it serves."""

    def test_refuses_to_start_when_unset_or_blank(self):
        for environ in ({}, {'DJANGO_ALLOWED_HOSTS': ''}, {'DJANGO_ALLOWED_HOSTS': ' , '}):
            with self.subTest(environ=environ), self.assertRaises(ImproperlyConfigured):
                allowed_hosts_from(environ, required=True)

    def test_reads_the_list_when_set(self):
        hosts = allowed_hosts_from({'DJANGO_ALLOWED_HOSTS': 'imaraworks.onrender.com'}, required=True)
        self.assertEqual(hosts, ['imaraworks.onrender.com'])


class DatabaseFromTests(SimpleTestCase):
    def test_reads_a_postgres_url(self):
        db = database_from({'DATABASE_URL': 'postgres://imara:pw@db.example.com:5432/imaraworks'})
        self.assertEqual(db['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual((db['NAME'], db['HOST'], db['PORT']), ('imaraworks', 'db.example.com', 5432))

    def test_refuses_to_start_when_unset_or_blank(self):
        for environ in ({}, {'DATABASE_URL': '   '}):
            with self.subTest(environ=environ), self.assertRaises(ImproperlyConfigured):
                database_from(environ)


class DevOnServerGuardTests(SimpleTestCase):
    """Dev settings must not run on the server, e.g. `manage.py migrate` without
    DJANGO_SETTINGS_MODULE: it would migrate a local SQLite file, not Postgres."""

    def test_refuses_when_database_url_is_set(self):
        with self.assertRaises(ImproperlyConfigured):
            refuse_dev_settings_on_server({'DATABASE_URL': 'postgres://x/y'})

    def test_allows_a_developer_machine(self):
        refuse_dev_settings_on_server({})   # no error


PROD_ENV = {
    'DJANGO_SECRET_KEY': 'a-real-random-key-for-the-demo',
    'DJANGO_ALLOWED_HOSTS': 'imaraworks.onrender.com',
    'DATABASE_URL': 'postgres://imara:pw@db.example.com:5432/imaraworks',
}


def load_settings(module, environ):
    """Import a settings module afresh with exactly ``environ`` as the environment."""
    with mock.patch.dict(os.environ, environ, clear=True):
        sys.modules.pop(module, None)
        try:
            return importlib.import_module(module)
        finally:
            sys.modules.pop(module, None)


class SettingsModuleTests(SimpleTestCase):
    """The modules really use the rules above."""

    def test_dev_debugs_on_sqlite_with_no_setup(self):
        dev = load_settings('imaraworks.settings.dev', {})
        self.assertTrue(dev.DEBUG)
        self.assertEqual(dev.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        self.assertEqual(dev.SECRET_KEY, DEV_SECRET_KEY)

    def test_dev_refuses_to_run_on_the_server(self):
        with self.assertRaises(ImproperlyConfigured):
            load_settings('imaraworks.settings.dev', {'DATABASE_URL': PROD_ENV['DATABASE_URL']})

    def test_prod_is_debug_off_and_fully_env_driven(self):
        prod = load_settings('imaraworks.settings.prod', {**PROD_ENV, 'DJANGO_DEBUG': '1'})
        self.assertFalse(prod.DEBUG)   # DJANGO_DEBUG can't switch it on
        self.assertEqual(prod.SECRET_KEY, PROD_ENV['DJANGO_SECRET_KEY'])
        self.assertEqual(prod.ALLOWED_HOSTS, ['imaraworks.onrender.com'])
        self.assertEqual(prod.DATABASES['default']['ENGINE'], 'django.db.backends.postgresql')

    def test_prod_refuses_to_start_without_each_required_variable(self):
        for missing in PROD_ENV:
            environ = {k: v for k, v in PROD_ENV.items() if k != missing}
            with self.subTest(missing=missing), self.assertRaises(ImproperlyConfigured):
                load_settings('imaraworks.settings.prod', environ)


class SettingsLayoutTests(SimpleTestCase):
    """Issue #24: settings are split into base, dev and prod."""

    def test_base_dir_is_the_project_root(self):
        # base.py sits one folder deeper than the old settings.py. If BASE_DIR
        # were not adjusted, the database and static paths would point inside
        # imaraworks/ instead of the project root.
        self.assertTrue((settings.BASE_DIR / 'manage.py').is_file())

    def test_manage_py_defaults_to_dev_and_server_entry_points_to_prod(self):
        root = settings.BASE_DIR
        expected = {
            'manage.py': 'imaraworks.settings.dev',
            'imaraworks/wsgi.py': 'imaraworks.settings.prod',
            'imaraworks/asgi.py': 'imaraworks.settings.prod',
        }
        for path, module in expected.items():
            with self.subTest(path=path):
                self.assertIn(f"'{module}'", (root / path).read_text(encoding='utf-8'))
