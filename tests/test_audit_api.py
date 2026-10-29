"""HTTP tests for the read-only audit endpoints (docs/API.md)."""

import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from apps.accounts.models import Profile
from apps.approvals.services import approve, reject
from apps.audit.models import AuditLog
from apps.payment_requests.models import PaymentRequest, Project
from apps.vendors.models import Vendor


def make_user(name, role):
    # No password: tests log in with force_authenticate, and hashing is slow.
    user = User.objects.create_user(name)
    Profile.objects.create(user=user, role=role)
    return user


class AuditApiTestCase(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.alice = make_user('alice', Profile.EMPLOYEE)
        cls.brian = make_user('brian', Profile.EMPLOYEE)
        cls.carol = make_user('carol', Profile.MANAGER)
        cls.faith = make_user('faith', Profile.FINANCE)
        cls.grace = make_user('grace', Profile.ADMIN)
        vendor = Vendor.objects.create(name='Nairobi Cement Ltd', service='Cement')
        project = Project.objects.create(name='Kilimani Apartments')
        cls.req = PaymentRequest.objects.create(
            vendor=vendor, project=project, requester=cls.alice,
            amount=Decimal('148000'), reason='Materials', invoice_number='INV-1',
            payment_method=PaymentRequest.MPESA, date=datetime.date(2026, 10, 14),
            status=PaymentRequest.PENDING_APPROVAL,
        )
        approve(cls.req, cls.carol)                       # entry 1: APPROVED
        reject(cls.req, cls.faith, 'Over the project budget')  # entry 2: REJECTED

    def as_user(self, user):
        self.client.force_authenticate(user)


class HistoryApiTests(AuditApiTestCase):

    def url(self, pk):
        return f'/api/payment-requests/{pk}/history/'

    def test_requester_sees_history_oldest_first(self):
        self.as_user(self.alice)
        resp = self.client.get(self.url(self.req.pk))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual([e['action'] for e in resp.data], [AuditLog.APPROVED, AuditLog.REJECTED])
        self.assertEqual(resp.data[0]['actor_username'], 'carol')
        self.assertEqual(resp.data[1]['details']['reason'], 'Over the project budget')
        self.assertEqual(set(resp.data[0]), {'id', 'action', 'actor_username', 'details', 'timestamp'})

    def test_manager_and_finance_see_history(self):
        for user in (self.carol, self.faith):
            self.as_user(user)
            self.assertEqual(self.client.get(self.url(self.req.pk)).status_code, 200)

    def test_others_get_404(self):
        # Brian can't see Alice's request; admins see no requests.
        for user in (self.brian, self.grace):
            self.as_user(user)
            self.assertEqual(self.client.get(self.url(self.req.pk)).status_code, 404)

    def test_unknown_request_is_404(self):
        self.as_user(self.carol)
        self.assertEqual(self.client.get(self.url(999)).status_code, 404)

    def test_requires_login(self):
        self.assertEqual(self.client.get(self.url(self.req.pk)).status_code, 401)


class AuditLogApiTests(AuditApiTestCase):
    url = '/api/audit/'

    def test_admin_sees_whole_log_newest_first(self):
        self.as_user(self.grace)
        resp = self.client.get(self.url)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual([e['action'] for e in resp.data], [AuditLog.REJECTED, AuditLog.APPROVED])
        self.assertEqual(resp.data[0]['request'], self.req.pk)

    def test_reader_roles_see_no_financial_details(self):
        # Admins can't see payment data here, so the log leaves out `details`,
        # which holds amounts and rejection reasons.
        self.as_user(self.grace)
        resp = self.client.get(self.url)

        self.assertEqual(
            set(resp.data[0]),
            {'id', 'action', 'actor_username', 'timestamp', 'request'},
        )
        self.assertNotIn('Over the project budget', str(resp.data))
        self.assertNotIn('148000', str(resp.data))

    def test_filter_by_action(self):
        self.as_user(self.grace)
        resp = self.client.get(self.url, {'action': AuditLog.APPROVED})
        self.assertEqual([e['action'] for e in resp.data], [AuditLog.APPROVED])

    def test_other_roles_get_403(self):
        for user in (self.alice, self.brian, self.carol, self.faith):
            with self.subTest(user=user.username):
                self.as_user(user)
                self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_log_is_read_only(self):
        self.as_user(self.grace)
        self.assertEqual(self.client.post(self.url, {}, format='json').status_code, 405)

    def test_requires_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
