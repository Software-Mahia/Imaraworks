"""
Issue #21: the seeded password123 is dev-only and must not reach the deployed demo.
"""

import os
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.accounts.models import Profile
from apps.payment_requests.management.commands.seed_users import DEV_PASSWORD


def seed(refresh=False):
    call_command('seed_users', refresh=refresh, stdout=StringIO())


class SeedPasswordTests(TestCase):
    @override_settings(DEBUG=True)
    @mock.patch.dict(os.environ, {}, clear=True)
    def test_dev_password_while_debugging(self):
        seed()
        self.assertTrue(User.objects.get(username='alice').check_password(DEV_PASSWORD))

    @override_settings(DEBUG=False)
    @mock.patch.dict(os.environ, {'SEED_USER_PASSWORD': 'demo-secret-pw'}, clear=True)
    def test_env_password_on_the_deployed_demo(self):
        seed()
        alice = User.objects.get(username='alice')
        self.assertTrue(alice.check_password('demo-secret-pw'))
        self.assertFalse(alice.check_password(DEV_PASSWORD))

    @override_settings(DEBUG=True)
    @mock.patch.dict(os.environ, {'SEED_USER_PASSWORD': 'demo-secret-pw'}, clear=True)
    def test_env_password_wins_even_while_debugging(self):
        seed()
        self.assertTrue(User.objects.get(username='alice').check_password('demo-secret-pw'))

    @override_settings(DEBUG=False)
    @mock.patch.dict(os.environ, {}, clear=True)
    def test_refuses_without_password_when_debug_is_off(self):
        with self.assertRaises(CommandError):
            seed()
        # Refused before creating anything, so no user has the dev password.
        self.assertFalse(User.objects.exists())

    @override_settings(DEBUG=False)
    @mock.patch.dict(os.environ, {'SEED_USER_PASSWORD': '  '}, clear=True)
    def test_blank_password_counts_as_unset(self):
        with self.assertRaises(CommandError):
            seed()


class SeedRefreshTests(TestCase):
    """A re-run is a no-op unless --refresh is passed (repairing a demo sign-in)."""

    @override_settings(DEBUG=False)
    @mock.patch.dict(os.environ, {'SEED_USER_PASSWORD': 'first-password'}, clear=True)
    def test_plain_rerun_leaves_an_existing_password_alone(self):
        seed()
        with mock.patch.dict(os.environ, {'SEED_USER_PASSWORD': 'second-password'}, clear=True):
            seed()
        alice = User.objects.get(username='alice')
        self.assertTrue(alice.check_password('first-password'))
        self.assertFalse(alice.check_password('second-password'))

    @override_settings(DEBUG=False)
    @mock.patch.dict(os.environ, {'SEED_USER_PASSWORD': 'first-password'}, clear=True)
    def test_refresh_resets_an_existing_password(self):
        seed()
        with mock.patch.dict(os.environ, {'SEED_USER_PASSWORD': 'second-password'}, clear=True):
            seed(refresh=True)
        for username in ('alice', 'faith', 'grace'):
            self.assertTrue(
                User.objects.get(username=username).check_password('second-password'),
                msg=f'{username} kept the old password after --refresh',
            )

    @override_settings(DEBUG=False)
    @mock.patch.dict(os.environ, {'SEED_USER_PASSWORD': 'demo-secret-pw'}, clear=True)
    def test_refresh_corrects_a_drifted_role(self):
        seed()
        profile = Profile.objects.get(user__username='faith')
        profile.role = Profile.EMPLOYEE
        profile.save(update_fields=['role'])

        seed(refresh=True)

        profile.refresh_from_db()
        self.assertEqual(profile.role, Profile.FINANCE)

    @override_settings(DEBUG=False)
    @mock.patch.dict(os.environ, {'SEED_USER_PASSWORD': 'demo-secret-pw'}, clear=True)
    def test_refresh_reactivates_an_existing_account(self):
        seed()
        User.objects.filter(username='grace').update(is_active=False)

        seed(refresh=True)

        self.assertTrue(User.objects.get(username='grace').is_active)

    @override_settings(DEBUG=False)
    @mock.patch.dict(os.environ, {'SEED_USER_PASSWORD': 'demo-secret-pw'}, clear=True)
    def test_refresh_does_not_touch_unrelated_accounts(self):
        User.objects.create_user(username='outsider', password='their-own-password')
        Profile.objects.create(user=User.objects.get(username='outsider'), role=Profile.EMPLOYEE)

        seed(refresh=True)

        outsider = User.objects.get(username='outsider')
        self.assertTrue(outsider.check_password('their-own-password'))
        self.assertEqual(outsider.profile.role, Profile.EMPLOYEE)
