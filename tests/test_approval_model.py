"""Database tests for the Approval model (apps/approvals/models.py).

TestCase (not SimpleTestCase) because these check constraints the database
itself enforces. They are the backstop behind the rules in services.py: even
if two approvers click at the same moment, or code skips the service, the
database refuses the bad row.
"""

import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.approvals.logic import LEVEL_FINANCE as F, LEVEL_MANAGER as M
from apps.approvals.models import Approval
from apps.payment_requests.models import PaymentRequest, Project
from apps.vendors.models import Vendor


class ApprovalModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user('alice')
        cls.carol = User.objects.create_user('carol')
        cls.david = User.objects.create_user('david')
        cls.request = PaymentRequest.objects.create(
            vendor=Vendor.objects.create(name='Nairobi Cement Ltd', service='Cement'),
            project=Project.objects.create(name='Kilimani Apartments'),
            requester=cls.alice,
            amount=Decimal('67000'),
            reason='Cement for phase 2',
            invoice_number='INV-001',
            payment_method=PaymentRequest.BANK_TRANSFER,
            date=datetime.date(2026, 10, 14),
            status=PaymentRequest.PENDING_APPROVAL,
        )

    def _approve(self, approver, level=M, **extra):
        return Approval.objects.create(request=self.request, approver=approver,
                                       decision=Approval.APPROVED, level=level, **extra)

    # --- One counting approval per level ---
    def test_second_active_approval_at_same_level_is_refused(self):
        self._approve(self.carol)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._approve(self.david)

    def test_different_levels_can_both_approve(self):
        self._approve(self.carol, level=M)
        self._approve(self.david, level=F)
        self.assertEqual(self.request.approvals.count(), 2)

    def test_reapproval_allowed_once_old_approval_is_superseded(self):
        # Amount change marks the old approval superseded; a fresh one may follow.
        old = self._approve(self.carol)
        old.superseded = True
        old.save()
        self._approve(self.carol)
        self.assertEqual(self.request.approvals.filter(superseded=False).count(), 1)

    # --- Rejections need a reason ---
    def test_rejection_without_reason_is_refused(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Approval.objects.create(request=self.request, approver=self.carol,
                                        decision=Approval.REJECTED, level=M)

    def test_rejection_with_reason_is_stored(self):
        a = Approval.objects.create(request=self.request, approver=self.carol,
                                    decision=Approval.REJECTED, level=M,
                                    reason='Invoice does not match delivery note')
        self.assertEqual(a.reason, 'Invoice does not match delivery note')

    def test_approval_without_reason_is_fine(self):
        self.assertEqual(self._approve(self.carol).reason, '')
