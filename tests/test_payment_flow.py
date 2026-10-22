"""End-to-end tests across Part B (approval) and Part C (payment).

Part C's own tests check payments alone. These check the hand-over: a request
is only ever paid once it is fully approved, it is paid exactly the approved
amount, it is paid once, and its history shows every step. Everything goes
through the real endpoints, as the pages would call them.

Scenarios are the ones agreed with Part C on PR #12, plus the payment
decisions on #33 (no paying your own request; a FAILED amount stays locked).
"""

import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from apps.accounts.models import Profile
from apps.audit.models import AuditLog
from apps.payment_requests.models import PaymentRequest, Project
from apps.payments.models import PaymentTransaction
from apps.vendors.models import Vendor


def make_user(name, role):
    # No password: tests log in with force_authenticate, and hashing is slow.
    user = User.objects.create_user(name)
    Profile.objects.create(user=user, role=role)
    return user


class PaymentFlowTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.alice = make_user('alice', Profile.EMPLOYEE)
        cls.carol = make_user('carol', Profile.MANAGER)
        cls.faith = make_user('faith', Profile.FINANCE)
        cls.fiona = make_user('fiona', Profile.FINANCE)   # a second Finance user, for scenario 10
        cls.grace = make_user('grace', Profile.ADMIN)
        cls.vendor = Vendor.objects.create(name='Nairobi Cement Ltd', service='Cement')
        cls.project = Project.objects.create(name='Kilimani Apartments')

    def make_request(self, amount, status=PaymentRequest.PENDING_APPROVAL, requester=None):
        return PaymentRequest.objects.create(
            vendor=self.vendor, project=self.project, requester=requester or self.alice,
            amount=Decimal(amount), reason='Materials',
            invoice_number=f'INV-{PaymentRequest.objects.count() + 1}',
            payment_method=PaymentRequest.MPESA,
            date=datetime.date(2026, 10, 19), status=status,
        )

    # --- helpers: each one is a single HTTP call, as the pages would make it ---

    def as_user(self, user):
        self.client.force_authenticate(user)

    def submit(self, req):
        self.as_user(self.alice)
        resp = self.client.post(f'/api/payment-requests/{req.pk}/submit/')
        self.assertEqual(resp.status_code, 200)

    def approve(self, user, req):
        self.as_user(user)
        resp = self.client.post(f'/api/payment-requests/{req.pk}/approve/')
        self.assertEqual(resp.status_code, 200)

    def reject(self, user, req, reason):
        self.as_user(user)
        resp = self.client.post(f'/api/payment-requests/{req.pk}/reject/', {'reason': reason}, format='json')
        self.assertEqual(resp.status_code, 200)

    def change_amount(self, req, amount):
        self.as_user(self.alice)
        return self.client.patch(f'/api/payment-requests/{req.pk}/amount/', {'amount': amount}, format='json')

    def pay(self, req, key=None, decline=False, payer=None):
        self.as_user(payer or self.faith)
        body = {}
        if key:
            body['idempotency_key'] = key
        if decline:
            body['description'] = 'FAIL'   # the mock gateway declines on "FAIL"
        return self.client.post(f'/api/payment-requests/{req.pk}/pay/', body, format='json')

    def status_of(self, req):
        req.refresh_from_db()
        return req.status

    def history(self, req):
        return self.history_as(self.alice, req)

    def history_as(self, user, req):
        self.as_user(user)
        return [e['action'] for e in self.client.get(f'/api/payment-requests/{req.pk}/history/').data]

    # --- 1. Only a fully approved request can be paid ---

    def test_large_request_with_only_manager_approval_cannot_be_paid(self):
        req = self.make_request('148000')
        self.approve(self.carol, req)          # finance has not approved yet

        resp = self.pay(req)

        self.assertEqual(resp.status_code, 409)
        self.assertFalse(PaymentTransaction.objects.filter(request=req).exists())
        self.assertEqual(self.status_of(req), PaymentRequest.PENDING_APPROVAL)

    # --- 2. The approved amount is what gets paid ---

    def test_approved_request_is_paid_its_approved_amount(self):
        req = self.make_request('24500')
        self.approve(self.carol, req)

        resp = self.pay(req)

        self.assertEqual(resp.status_code, 201)
        self.assertEqual((resp.data['status'], resp.data['amount']), (PaymentTransaction.SUCCESS, '24500.00'))
        self.assertEqual(self.status_of(req), PaymentRequest.PAID)

    # --- 3. An amount change after approval must be re-approved before paying ---

    def test_raised_amount_must_be_reapproved_then_pays_the_new_amount(self):
        req = self.make_request('42000')
        self.approve(self.carol, req)
        self.assertEqual(self.change_amount(req, '67000').status_code, 200)

        resp = self.pay(req)                   # old approval no longer counts
        self.assertEqual(resp.status_code, 409)
        self.assertFalse(PaymentTransaction.objects.filter(request=req).exists())

        self.approve(self.carol, req)          # 67,000 needs manager AND finance
        self.approve(self.faith, req)
        resp = self.pay(req)

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['amount'], '67000.00')

    # --- 4. Once payment has started, the amount is locked (FAILED too, #33) ---

    def test_amount_is_locked_once_payment_has_started(self):
        for status in (PaymentRequest.PROCESSING, PaymentRequest.PAID, PaymentRequest.FAILED):
            with self.subTest(status=status):
                req = self.make_request('24500', status=status)

                resp = self.change_amount(req, '30000')

                self.assertEqual(resp.status_code, 409)
                req.refresh_from_db()
                self.assertEqual(req.amount, Decimal('24500'))

    # --- 5. A rejected request is never paid ---

    def test_rejected_request_cannot_be_paid(self):
        req = self.make_request('42000')
        self.reject(self.carol, req, 'Invoice does not match delivery note')

        resp = self.pay(req)

        self.assertEqual(resp.status_code, 409)
        self.assertFalse(PaymentTransaction.objects.filter(request=req).exists())
        self.assertEqual(self.status_of(req), PaymentRequest.REJECTED)

    # --- 6. A declined payment can be retried, and is paid only once ---

    def test_declined_payment_is_retried_and_paid_once(self):
        req = self.make_request('24500')
        self.approve(self.carol, req)

        resp = self.pay(req, decline=True)
        self.assertEqual((resp.status_code, resp.data['status']), (201, PaymentTransaction.FAILED))
        self.assertEqual(self.status_of(req), PaymentRequest.FAILED)

        resp = self.pay(req)
        self.assertEqual((resp.status_code, resp.data['status']), (201, PaymentTransaction.SUCCESS))
        self.assertEqual(self.status_of(req), PaymentRequest.PAID)

        txns = PaymentTransaction.objects.filter(request=req)
        self.assertEqual(txns.count(), 2)
        self.assertEqual(txns.filter(status=PaymentTransaction.SUCCESS).count(), 1)

    # --- 7. Idempotency: a repeated click never pays twice ---

    def test_same_key_replays_and_new_key_after_paid_is_refused(self):
        req = self.make_request('24500')
        self.approve(self.carol, req)

        first = self.pay(req, key='click-1')
        again = self.pay(req, key='click-1')   # double click, same key
        self.assertEqual((first.status_code, again.status_code), (201, 200))
        self.assertTrue(again.data['replayed'])
        self.assertEqual(again.data['id'], first.data['id'])

        other = self.pay(req, key='click-2')   # a fresh attempt once it is PAID
        self.assertEqual(other.status_code, 409)
        self.assertEqual(PaymentTransaction.objects.filter(request=req).count(), 1)

    # --- 8. The history shows every step, in order ---

    def test_history_records_the_whole_journey(self):
        req = self.make_request('24500', status=PaymentRequest.DRAFT)
        self.submit(req)
        self.approve(self.carol, req)
        self.pay(req, decline=True)
        self.pay(req)

        self.assertEqual(self.history(req), [
            AuditLog.SUBMITTED, AuditLog.APPROVED,
            AuditLog.PAYMENT_STARTED, AuditLog.PAYMENT_FAILED,
            AuditLog.PAYMENT_STARTED, AuditLog.PAID,
        ])

    # --- 9. The admin log lists payment entries without their details ---

    def test_admin_log_lists_payment_entries_without_details(self):
        req = self.make_request('24500')
        self.approve(self.carol, req)
        self.pay(req)

        self.as_user(self.grace)
        entries = self.client.get('/api/audit/').data

        actions = {e['action'] for e in entries}
        self.assertTrue({AuditLog.PAYMENT_STARTED, AuditLog.PAID} <= actions)
        self.assertTrue(all('details' not in e for e in entries))

    # --- 10. Finance cannot pay a request they raised (#33) ---

    def test_finance_cannot_pay_their_own_request(self):
        # 24,500 needs only the manager, so faith's own request can be fully approved.
        req = self.make_request('24500', requester=self.faith)
        self.approve(self.carol, req)

        resp = self.pay(req)                   # faith pays her own request

        self.assertEqual(resp.status_code, 403)
        self.assertFalse(PaymentTransaction.objects.filter(request=req).exists())
        self.assertEqual(self.status_of(req), PaymentRequest.APPROVED)
        self.assertNotIn(AuditLog.PAYMENT_STARTED, self.history_as(self.faith, req))

        resp = self.pay(req, payer=self.fiona)  # another Finance user may pay it
        self.assertEqual((resp.status_code, resp.data['status']), (201, PaymentTransaction.SUCCESS))
        self.assertEqual(self.status_of(req), PaymentRequest.PAID)
