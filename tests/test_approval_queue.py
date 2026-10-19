"""Database tests for approval_summary() and approval_queue() (apps/approvals/services.py)."""

import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import Profile
from apps.approvals.logic import LEVEL_FINANCE as F, LEVEL_MANAGER as M
from apps.approvals.models import Approval
from apps.approvals.services import approval_queue, approval_summary, approve
from apps.payment_requests.models import PaymentRequest, Project
from apps.vendors.models import Vendor


def make_user(name, role):
    # No password: tests never log in, and hashing one per user is slow.
    user = User.objects.create_user(name)
    Profile.objects.create(user=user, role=role)
    return user


class ApprovalQueueTests(TestCase):

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

    # --- approval_summary ---
    def test_summary_small_request(self):
        req = self.make_request('24500')
        self.assertEqual(approval_summary(req), {
            'required_levels': [M], 'approved_levels': [], 'outstanding_levels': [M],
        })

    def test_summary_large_request_after_manager(self):
        req = self.make_request('148000')
        approve(req, self.carol)
        self.assertEqual(approval_summary(req), {
            'required_levels': [F, M], 'approved_levels': [M], 'outstanding_levels': [F],
        })

    def test_summary_ignores_superseded_approvals(self):
        req = self.make_request('24500')
        Approval.objects.create(request=req, approver=self.carol, decision=Approval.APPROVED,
                                level=M, superseded=True)
        self.assertEqual(approval_summary(req)['outstanding_levels'], [M])

    # --- approval_queue ---
    def test_manager_sees_pending_requests_oldest_first(self):
        first = self.make_request('24500')
        second = self.make_request('67000')
        self.assertEqual(approval_queue(self.carol), [first, second])

    def test_finance_sees_only_requests_over_50000(self):
        self.make_request('42000')
        big = self.make_request('67000')
        self.assertEqual(approval_queue(self.faith), [big])

    def test_own_requests_are_not_in_queue(self):
        self.make_request('24500', requester=self.carol)
        self.assertEqual(approval_queue(self.carol), [])

    def test_only_pending_requests_are_in_queue(self):
        self.make_request('24500', status=PaymentRequest.DRAFT)
        self.make_request('24500', status=PaymentRequest.APPROVED)
        self.assertEqual(approval_queue(self.carol), [])

    def test_request_leaves_queue_once_its_level_has_approved(self):
        req = self.make_request('67000')
        approve(req, self.carol)
        # Any manager is done with it, but it is still waiting on finance.
        self.assertEqual(approval_queue(self.david), [])
        self.assertEqual(approval_queue(self.faith), [req])

    def test_employee_and_admin_have_empty_queue(self):
        self.make_request('24500', requester=self.carol)
        self.assertEqual(approval_queue(self.alice), [])
        self.assertEqual(approval_queue(self.grace), [])
