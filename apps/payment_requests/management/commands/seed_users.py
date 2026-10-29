import os

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Profile
from apps.vendors.models import Vendor
from apps.payment_requests.models import Project

# The shared dev password from the case study. Only used while DEBUG is on, so
# it can never reach the deployed demo (issue #21).
DEV_PASSWORD = 'password123'


def seed_password(environ, *, debug):
    """SEED_USER_PASSWORD if set; the dev password only while debugging; otherwise refuse."""
    password = environ.get('SEED_USER_PASSWORD', '').strip()
    if password:
        return password
    if debug:
        return DEV_PASSWORD
    raise CommandError(
        'SEED_USER_PASSWORD is not set. The deployed demo must not use the dev '
        'password; set SEED_USER_PASSWORD. (Locally, the dev settings use the dev password.)'
    )


class Command(BaseCommand):
    help = 'Seeds sample users, vendors and projects from the case study'

    def add_arguments(self, parser):
        parser.add_argument(
            '--refresh',
            action='store_true',
            help=(
                "Also reset the seed users' passwords to SEED_USER_PASSWORD and correct "
                'their roles. Existing accounts are left untouched without this flag, so '
                'changing the environment variable alone does not repair old sign-ins.'
            ),
        )

    def handle(self, *args, refresh=False, **kwargs):
        # Decide the password before creating anything, so a refused run seeds nothing.
        password = seed_password(os.environ, debug=settings.DEBUG)
        users_data = [
            ('alice', 'Alice Mwangi', Profile.EMPLOYEE),
            ('brian', 'Brian Otieno', Profile.EMPLOYEE),
            ('carol', 'Carol Wanjiku', Profile.MANAGER),
            ('david', 'David Mutua', Profile.MANAGER),
            ('faith', 'Faith Njeri', Profile.FINANCE),
            # A second Finance officer, so faith's own requests can still get a
            # finance approval and be paid (#15, #33).
            ('fiona', 'Fiona Achieng', Profile.FINANCE),
            ('grace', 'Grace Kamau', Profile.ADMIN),
        ]
        for username, full_name, role in users_data:
            first, last = full_name.split(' ', 1)
            user, created = User.objects.get_or_create(
                username=username, defaults={'first_name': first, 'last_name': last}
            )
            # A plain re-run must never overwrite a working account, so the
            # update only happens for new users or an explicit --refresh.
            if created or refresh:
                user.first_name = first
                user.last_name = last
                user.is_active = True
                user.set_password(password)
                user.save()
            profile, _ = Profile.objects.get_or_create(user=user, defaults={'role': role})
            if refresh and profile.role != role:
                profile.role = role
                profile.save(update_fields=['role'])
            if created:
                status = 'Created'
            elif refresh:
                status = 'Refreshed'
            else:
                status = 'Already exists'
            self.stdout.write(f'{status}: {username} ({role})')

        vendors_data = [
            ('Metro Hardware Ltd.', 'Construction materials'),
            ('Prime Cement Supplies', 'Cement'),
            ('SwiftHaul Logistics', 'Transport'),
            ('PowerHire Kenya', 'Equipment rental'),
            ('Apex Electricals', 'Electrical materials'),
            ('BlueLine Plumbing', 'Plumbing services'),
        ]
        for name, service in vendors_data:
            _, created = Vendor.objects.get_or_create(name=name, defaults={'service': service})
            self.stdout.write(f"{'Created' if created else 'Already exists'}: vendor {name}")

        for name in ['Westlands Project', 'Mombasa Road Project', 'Kisumu Project']:
            _, created = Project.objects.get_or_create(name=name)
            self.stdout.write(f"{'Created' if created else 'Already exists'}: project {name}")