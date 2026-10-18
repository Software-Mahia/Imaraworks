"""HTTP tests for the approvals endpoints (docs/APPROVALS_API.md).

The rules are tested in the service tests. These check the HTTP layer: routes,
status codes, response shapes, and that each refusal maps to the documented code.
"""

import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from apps.accounts.models import Profile
from apps.approvals import logic
from apps.approvals.logic import LEVEL_FINANCE as F, LEVEL_MANAGER as M
from apps.approvals.services import MSG_REASON_REQUIRED
from apps.payment_requests.models import PaymentRequest, Project
from apps.vendors.models import Vendor


def make_user(name, role):
    # No password: tests log in with force_authenticate, and hashing is slow.
    user = User.objects.create_user(name)
    Profile.objects.create(user=user, role=role)
    return user


class ApprovalsApiTestCase(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.alice = make_user('alice', Profile.EMPLOYEE)
        cls.brian = make_user('brian', Profile.EMPLOYEE)
        cls.carol = make_user('carol', Profile.MANAGER)
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

    def as_user(self, user):
        self.client.force_authenticate(user)

    def approve_url(self, req):
        return f'/api/payment-requests/{req.pk}/approve/'

    def reject_url(self, req):
        return f'/api/payment-requests/{req.pk}/reject/'


class QueueApiTests(ApprovalsApiTestCase):
    url = '/api/approvals/queue/'

    def test_requires_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_manager_gets_queue_with_approval_block(self):
        req = self.make_request('67000')
        self.as_user(self.carol)
        resp = self.client.get(self.url)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        item = resp.data[0]
        self.assertEqual((item['id'], item['status']), (req.pk, PaymentRequest.PENDING_APPROVAL))
        self.assertEqual(item['approval'], {
            'required_levels': [F, M], 'approved_levels': [], 'outstanding_levels': [F, M],
        })

    def test_employee_and_admin_get_403(self):
        for user in (self.alice, self.grace):
            self.as_user(user)
            resp = self.client.get(self.url)
            self.assertEqual(resp.status_code, 403)
            self.assertEqual(resp.data['detail'], logic.MSG_ROLE_CANNOT)


class ApproveApiTests(ApprovalsApiTestCase):

    def test_requires_login(self):
        req = self.make_request('24500')
        self.assertEqual(self.client.post(self.approve_url(req)).status_code, 401)

    def test_manager_approves_small_request(self):
        req = self.make_request('24500')
        self.as_user(self.carol)
        resp = self.client.post(self.approve_url(req))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, {
            'id': req.pk, 'status': PaymentRequest.APPROVED,
            'approval': {'required_levels': [M], 'approved_levels': [M], 'outstanding_levels': []},
        })

    def test_large_request_stays_pending_after_manager(self):
        req = self.make_request('148000')
        self.as_user(self.carol)
        resp = self.client.post(self.approve_url(req))
        self.assertEqual(resp.data['status'], PaymentRequest.PENDING_APPROVAL)
        self.assertEqual(resp.data['approval']['outstanding_levels'], [F])

    def test_unknown_request_is_404(self):
        self.as_user(self.carol)
        self.assertEqual(self.client.post('/api/payment-requests/999/approve/').status_code, 404)

    def test_request_you_cannot_see_is_404(self):
        # Brian can't see Alice's request, so he gets 404, not 403.
        req = self.make_request('24500')
        self.as_user(self.brian)
        self.assertEqual(self.client.post(self.approve_url(req)).status_code, 404)

    def test_admin_gets_404(self):
        # Admins see no payment requests, so the 404 check comes first.
        req = self.make_request('24500')
        self.as_user(self.grace)
        self.assertEqual(self.client.post(self.approve_url(req)).status_code, 404)

    def test_each_refusal_maps_to_its_status(self):
        cases = [
            # (who, request, expected status, expected detail)
            (self.alice, self.make_request('24500', requester=self.alice), 403, logic.MSG_ROLE_CANNOT),
            (self.carol, self.make_request('24500', status=PaymentRequest.DRAFT), 409, logic.MSG_NOT_PENDING),
            (self.carol, self.make_request('24500', requester=self.carol), 403, logic.MSG_SELF_APPROVAL),
            (self.faith, self.make_request('42000'), 403, logic.MSG_NOT_REQUIRED),
        ]
        for user, req, code, detail in cases:
            with self.subTest(detail=detail):
                self.as_user(user)
                resp = self.client.post(self.approve_url(req))
                self.assertEqual(resp.status_code, code)
                self.assertEqual(resp.data['detail'], detail)

    def test_approving_twice_is_409(self):
        req = self.make_request('67000')
        self.as_user(self.carol)
        self.client.post(self.approve_url(req))
        resp = self.client.post(self.approve_url(req))
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data['detail'], logic.MSG_ALREADY_APPROVED)


class RejectApiTests(ApprovalsApiTestCase):

    def test_manager_rejects_with_reason(self):
        req = self.make_request('42000')
        self.as_user(self.carol)
        resp = self.client.post(self.reject_url(req), {'reason': '  Duplicate invoice '}, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, {
            'id': req.pk, 'status': PaymentRequest.REJECTED, 'reason': 'Duplicate invoice',
            'approval': {'required_levels': [M], 'approved_levels': [], 'outstanding_levels': [M]},
        })

    def test_missing_or_blank_reason_is_400(self):
        req = self.make_request('42000')
        self.as_user(self.carol)
        for body in ({}, {'reason': ''}, {'reason': '   '}, {'reason': 123}):
            with self.subTest(body=body):
                resp = self.client.post(self.reject_url(req), body, format='json')
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(resp.data['detail'], MSG_REASON_REQUIRED)
        req.refresh_from_db()
        self.assertEqual(req.status, PaymentRequest.PENDING_APPROVAL)

    def test_permission_checked_before_reason(self):
        # Self-rejection with no reason: told "not you", not "add a reason".
        req = self.make_request('42000', requester=self.carol)
        self.as_user(self.carol)
        resp = self.client.post(self.reject_url(req), {}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data['detail'], logic.MSG_SELF_APPROVAL)

    def test_rejecting_a_rejected_request_is_409(self):
        req = self.make_request('42000', status=PaymentRequest.REJECTED)
        self.as_user(self.carol)
        resp = self.client.post(self.reject_url(req), {'reason': 'Again'}, format='json')
        self.assertEqual(resp.status_code, 409)
