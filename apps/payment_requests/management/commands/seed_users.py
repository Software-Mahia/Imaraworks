from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from apps.accounts.models import Profile
from apps.vendors.models import Vendor
from apps.payment_requests.models import Project


class Command(BaseCommand):
    help = 'Seeds sample users, vendors and projects from the case study'

    def handle(self, *args, **kwargs):
        users_data = [
            ('alice', 'Alice Mwangi', Profile.EMPLOYEE),
            ('brian', 'Brian Otieno', Profile.EMPLOYEE),
            ('carol', 'Carol Wanjiku', Profile.MANAGER),
            ('david', 'David Mutua', Profile.MANAGER),
            ('faith', 'Faith Njeri', Profile.FINANCE),
            ('grace', 'Grace Kamau', Profile.ADMIN),
        ]
        for username, full_name, role in users_data:
            first, last = full_name.split(' ', 1)
            user, created = User.objects.get_or_create(
                username=username, defaults={'first_name': first, 'last_name': last}
            )
            if created:
                user.set_password('password123')
                user.save()
            Profile.objects.get_or_create(user=user, defaults={'role': role})
            self.stdout.write(f"{'Created' if created else 'Already exists'}: {username} ({role})")

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