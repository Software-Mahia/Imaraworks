"""Django admin must not rewrite approval or audit history.

Approval rows and audit entries are history: an approval is only ever marked
superseded by change_amount(), and the audit log is append-only. The admin is
for looking, not editing. Tested as a superuser, who skips every normal
permission check, so if a superuser can't change a row, nobody can.
"""

import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from apps.approvals.logic import LEVEL_MANAGER as M
from apps.approvals.models import Approval
from apps.audit.models import AuditLog
from apps.payment_requests.models import PaymentRequest, Project
from apps.vendors.models import Vendor


class AdminReadOnlyTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.root = User.objects.create_superuser('root', password='unused-in-tests')
        cls.alice = User.objects.create_user('alice')
        cls.carol = User.objects.create_user('carol')
        cls.request = PaymentRequest.objects.create(
            vendor=Vendor.objects.create(name='Nairobi Cement Ltd', service='Cement'),
            project=Project.objects.create(name='Kilimani Apartments'),
            requester=cls.alice,
            amount=Decimal('42000'),
            reason='Cement for phase 1',
            invoice_number='INV-001',
            payment_method=PaymentRequest.MPESA,
            date=datetime.date(2026, 10, 14),
            status=PaymentRequest.REJECTED,
        )
        cls.approval = Approval.objects.create(
            request=cls.request, approver=cls.carol, decision=Approval.REJECTED,
            level=M, reason='Invoice does not match delivery note',
        )
        cls.entry = AuditLog.objects.create(
            request=cls.request, actor=cls.carol, action=AuditLog.REJECTED,
        )

    def setUp(self):
        self.client.force_login(self.root)

    def urls_for(self, model, obj):
        base = f'/admin/{model._meta.app_label}/{model._meta.model_name}/'
        return base, f'{base}{obj.pk}/change/', f'{base}{obj.pk}/delete/', f'{base}add/'

    def assert_read_only(self, model, obj, change_data):
        changelist, change, delete, add = self.urls_for(model, obj)

        # Looking is allowed.
        self.assertEqual(self.client.get(changelist).status_code, 200)
        self.assertEqual(self.client.get(change).status_code, 200)

        # Changing, deleting and adding are not.
        self.assertEqual(self.client.post(change, change_data).status_code, 403)
        self.assertEqual(self.client.post(delete, {'post': 'yes'}).status_code, 403)
        self.assertEqual(self.client.get(add).status_code, 403)

    def test_approval_admin_is_read_only(self):
        # The edit that matters most: turning a rejection into an approval.
        self.assert_read_only(Approval, self.approval, {
            'request': self.request.pk, 'approver': self.carol.pk,
            'decision': Approval.APPROVED, 'level': M, 'reason': '',
        })
        self.approval.refresh_from_db()
        self.assertEqual(self.approval.decision, Approval.REJECTED)
        self.assertFalse(self.approval.superseded)

    def test_audit_log_admin_is_read_only(self):
        self.assert_read_only(AuditLog, self.entry, {
            'request': self.request.pk, 'actor': self.carol.pk,
            'action': AuditLog.APPROVED, 'details': '{}',
        })
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.action, AuditLog.REJECTED)
