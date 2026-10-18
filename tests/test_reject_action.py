"""Database tests for the reject save step (apps/approvals/services.py: reject).

The rules are covered in test_approval_services.py. These check that a
rejection is stored with its reason and audited, and that a refused rejection
writes nothing.
"""

import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import Profile
from apps.approvals import logic
from apps.approvals.logic import LEVEL_FINANCE as F, LEVEL_MANAGER as M
from apps.approvals.models import Approval
from apps.approvals.services import MSG_REASON_REQUIRED, ApprovalDenied, approve, reject
from apps.audit.models import AuditLog
from apps.payment_requests.models import PaymentRequest, Project
from apps.vendors.models import Vendor


def make_user(name, role):
    # No password: tests never log in, and hashing one per user is slow.
    user = User.objects.create_user(name)
    Profile.objects.create(user=user, role=role)
    return user


class RejectActionTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.alice = make_user('alice', Profile.EMPLOYEE)
        cls.carol = make_user('carol', Profile.MANAGER)
        cls.faith = make_user('faith', Profile.FINANCE)
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

    # --- A rejection is stored and audited ---
    def test_manager_rejects_with_reason(self):
        req = self.make_request('42000')
        reject(req, self.carol, 'Invoice does not match the delivery note')

        req.refresh_from_db()
        self.assertEqual(req.status, PaymentRequest.REJECTED)
        row = req.approvals.get()
        self.assertEqual((row.approver, row.decision, row.level), (self.carol, Approval.REJECTED, M))
        self.assertEqual(row.reason, 'Invoice does not match the delivery note')

    def test_rejection_writes_audit_entry_with_reason(self):
        req = self.make_request('42000')
        reject(req, self.carol, 'Duplicate invoice')

        entry = req.audit_logs.get()
        self.assertEqual((entry.actor, entry.action), (self.carol, AuditLog.REJECTED))
        self.assertEqual(entry.details, {'level': M, 'amount': '42000.00', 'reason': 'Duplicate invoice'})

    def test_reason_is_trimmed(self):
        req = self.make_request('42000')
        reject(req, self.carol, '   Wrong vendor  ')
        self.assertEqual(req.approvals.get().reason, 'Wrong vendor')

    def test_finance_rejects_after_manager_approved(self):
        # One rejection at any level ends the request, even if a manager approved.
        req = self.make_request('148000')
        approve(req, self.carol)
        reject(req, self.faith, 'Over the project budget')

        req.refresh_from_db()
        self.assertEqual(req.status, PaymentRequest.REJECTED)
        self.assertEqual(req.approvals.get(decision=Approval.REJECTED).level, F)
        self.assertEqual(req.audit_logs.count(), 2)

    # --- Refusals write nothing ---
    def test_blank_reason_is_refused(self):
        req = self.make_request('42000')
        for blank in ('', '   ', None):
            with self.assertRaises(ApprovalDenied) as ctx:
                reject(req, self.carol, blank)
            self.assertEqual(ctx.exception.reason, MSG_REASON_REQUIRED)
        self.assert_nothing_written(req)

    def test_cannot_reject_own_request(self):
        req = self.make_request('42000', requester=self.carol)
        with self.assertRaises(ApprovalDenied) as ctx:
            reject(req, self.carol, 'Changed my mind')
        self.assertEqual(ctx.exception.reason, logic.MSG_SELF_APPROVAL)
        self.assert_nothing_written(req)

    def test_employee_cannot_reject(self):
        req = self.make_request('42000', requester=self.carol)
        with self.assertRaises(ApprovalDenied) as ctx:
            reject(req, self.alice, 'Too expensive')
        self.assertEqual(ctx.exception.reason, logic.MSG_ROLE_CANNOT)
        self.assert_nothing_written(req)

    def test_already_rejected_request_cannot_be_rejected_again(self):
        req = self.make_request('42000')
        reject(req, self.carol, 'Duplicate invoice')
        with self.assertRaises(ApprovalDenied) as ctx:
            reject(req, self.carol, 'Still a duplicate')
        self.assertEqual(ctx.exception.reason, logic.MSG_NOT_PENDING)
        self.assertEqual(req.approvals.count(), 1)

    def test_rejected_request_cannot_then_be_approved(self):
        req = self.make_request('42000')
        reject(req, self.carol, 'Duplicate invoice')
        with self.assertRaises(ApprovalDenied):
            approve(req, self.carol)
