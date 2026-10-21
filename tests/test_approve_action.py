"""Database tests for the approve save step (apps/approvals/services.py: approve).

The rules themselves are covered in test_approval_logic.py and
test_approval_services.py. These check the saving: the right rows are written
when allowed, and NOTHING is written when refused.
"""

import datetime
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import Profile
from apps.approvals import logic
from apps.approvals.logic import LEVEL_FINANCE as F, LEVEL_MANAGER as M
from apps.approvals.models import Approval
from apps.approvals.services import ApprovalDenied, approve
from apps.audit.models import AuditLog
from apps.payment_requests.models import PaymentRequest, Project
from apps.vendors.models import Vendor


def make_user(name, role):
    # No password: tests never log in, and hashing one per user is slow.
    user = User.objects.create_user(name)
    Profile.objects.create(user=user, role=role)
    return user


class ApproveActionTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.alice = make_user('alice', Profile.EMPLOYEE)
        cls.carol = make_user('carol', Profile.MANAGER)
        cls.david = make_user('david', Profile.MANAGER)
        cls.faith = make_user('faith', Profile.FINANCE)
        cls.grace = make_user('grace', Profile.ADMIN)
        cls.vendor = Vendor.objects.create(name='Nairobi Cement Ltd', service='Cement')
        cls.project = Project.objects.create(name='Kilimani Apartments')

    def make_request(self, amount, requester=None, status=PaymentRequest.PENDING_APPROVAL):
        return PaymentRequest.objects.create(
            vendor=self.vendor, project=self.project,
            requester=requester or self.alice,
            amount=Decimal(amount), reason='Materials',
            invoice_number=f'INV-{PaymentRequest.objects.count() + 1}',
            payment_method=PaymentRequest.MPESA,
            date=datetime.date(2026, 10, 14), status=status,
        )

    def assert_nothing_written(self, req, status=PaymentRequest.PENDING_APPROVAL):
        req.refresh_from_db()
        self.assertEqual(req.status, status)
        self.assertFalse(req.approvals.exists())
        self.assertFalse(req.audit_logs.exists())

    # --- <= 50k: one manager is enough ---
    def test_manager_approves_24500_and_it_is_approved(self):
        req = self.make_request('24500')
        decision = approve(req, self.carol)

        req.refresh_from_db()
        self.assertEqual(req.status, PaymentRequest.APPROVED)
        self.assertEqual(decision.level, M)
        row = req.approvals.get()
        self.assertEqual((row.approver, row.decision, row.level), (self.carol, Approval.APPROVED, M))

    def test_approval_writes_one_audit_entry(self):
        req = self.make_request('24500')
        approve(req, self.carol)

        entry = req.audit_logs.get()
        self.assertEqual((entry.actor, entry.action), (self.carol, AuditLog.APPROVED))
        self.assertEqual(entry.details, {'level': M, 'amount': '24500.00', 'fully_approved': True})

    # --- > 50k: manager AND finance, either order ---
    def test_67000_needs_manager_and_finance(self):
        req = self.make_request('67000')

        approve(req, self.carol)
        req.refresh_from_db()
        self.assertEqual(req.status, PaymentRequest.PENDING_APPROVAL)

        approve(req, self.faith)
        req.refresh_from_db()
        self.assertEqual(req.status, PaymentRequest.APPROVED)
        self.assertEqual(set(req.approvals.values_list('level', flat=True)), {M, F})
        self.assertEqual(req.audit_logs.count(), 2)

    def test_148000_finance_first_then_manager(self):
        req = self.make_request('148000')
        approve(req, self.faith)
        approve(req, self.carol)
        req.refresh_from_db()
        self.assertEqual(req.status, PaymentRequest.APPROVED)

    # --- Refusals write nothing ---
    def test_self_approval_is_refused_and_nothing_written(self):
        req = self.make_request('24500', requester=self.carol)
        with self.assertRaises(ApprovalDenied) as ctx:
            approve(req, self.carol)
        self.assertEqual(ctx.exception.reason, logic.MSG_SELF_APPROVAL)
        self.assert_nothing_written(req)

    def test_employee_cannot_approve(self):
        req = self.make_request('24500', requester=self.carol)
        with self.assertRaises(ApprovalDenied) as ctx:
            approve(req, self.alice)
        self.assertEqual(ctx.exception.reason, logic.MSG_ROLE_CANNOT)
        self.assert_nothing_written(req)

    def test_admin_cannot_approve(self):
        req = self.make_request('24500')
        with self.assertRaises(ApprovalDenied):
            approve(req, self.grace)
        self.assert_nothing_written(req)

    def test_user_without_profile_cannot_approve(self):
        nobody = User.objects.create_user('nobody')
        req = self.make_request('24500')
        with self.assertRaises(ApprovalDenied) as ctx:
            approve(req, nobody)
        self.assertEqual(ctx.exception.reason, logic.MSG_ROLE_CANNOT)

    def test_finance_not_needed_at_or_below_50000(self):
        req = self.make_request('50000')
        with self.assertRaises(ApprovalDenied) as ctx:
            approve(req, self.faith)
        self.assertEqual(ctx.exception.reason, logic.MSG_NOT_REQUIRED)
        self.assert_nothing_written(req)

    def test_draft_cannot_be_approved(self):
        req = self.make_request('24500', status=PaymentRequest.DRAFT)
        with self.assertRaises(ApprovalDenied) as ctx:
            approve(req, self.carol)
        self.assertEqual(ctx.exception.reason, logic.MSG_NOT_PENDING)
        self.assert_nothing_written(req, status=PaymentRequest.DRAFT)

    def test_second_manager_cannot_approve_same_level(self):
        req = self.make_request('67000')
        approve(req, self.carol)
        with self.assertRaises(ApprovalDenied) as ctx:
            approve(req, self.david)
        self.assertEqual(ctx.exception.reason, logic.MSG_ALREADY_APPROVED)
        self.assertEqual(req.approvals.count(), 1)
        self.assertEqual(req.audit_logs.count(), 1)

    # --- Reads fresh state, not the object passed in ---
    def test_uses_current_status_not_stale_object(self):
        req = self.make_request('24500')
        PaymentRequest.objects.filter(pk=req.pk).update(status=PaymentRequest.REJECTED)
        # `req` in memory still says PENDING_APPROVAL; the database says REJECTED.
        with self.assertRaises(ApprovalDenied) as ctx:
            approve(req, self.carol)
        self.assertEqual(ctx.exception.reason, logic.MSG_NOT_PENDING)

    def test_superseded_approval_does_not_count(self):
        # After an amount change the old approval is superseded; a fresh one is needed.
        req = self.make_request('24500')
        Approval.objects.create(request=req, approver=self.carol, decision=Approval.APPROVED,
                                level=M, superseded=True)
        approve(req, self.carol)
        req.refresh_from_db()
        self.assertEqual(req.status, PaymentRequest.APPROVED)

    # --- Two approvers at once: the database backstop ---
    def test_constraint_clash_is_already_approved_and_nothing_written(self):
        # Simulates two managers approving at the same moment without the row
        # lock: david's check reads "no manager approval yet", but carol's row
        # is already saved, so the database constraint refuses david's.
        req = self.make_request('67000')
        approve(req, self.carol)
        with mock.patch('apps.approvals.services._counting_levels', return_value=set()):
            with self.assertRaises(ApprovalDenied) as ctx:
                approve(req, self.david)
        self.assertEqual(ctx.exception.reason, logic.MSG_ALREADY_APPROVED)
        self.assertEqual(req.approvals.count(), 1)
        self.assertEqual(req.audit_logs.count(), 1)
