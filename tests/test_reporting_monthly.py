"""The dashboard's 6-month series: requests raised and money paid per month.

Fixed dates, not "today", so the test gives the same answer forever.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import Profile
from apps.payment_requests.models import PaymentRequest, Project
from apps.payments.models import PaymentTransaction
from apps.reporting.services import summary, totals_by_month
from apps.vendors.models import Vendor

EAT = timezone(timedelta(hours=3))
TODAY = date(2026, 10, 15)


class MonthlyTotalsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice')
        Profile.objects.create(user=self.user, role=Profile.EMPLOYEE)
        self.vendor = Vendor.objects.create(name='Metro Hardware Ltd.', service='Materials')
        self.project = Project.objects.create(name='Westlands Project')

    def make_request(self, amount, day, status=PaymentRequest.PAID, invoice='INV-1'):
        return PaymentRequest.objects.create(
            requester=self.user, vendor=self.vendor, project=self.project,
            amount=Decimal(amount), status=status, reason='Site materials',
            invoice_number=invoice, payment_method=PaymentRequest.MPESA, date=day,
        )

    def pay(self, request, amount, when):
        return PaymentTransaction.objects.create(
            request=request, idempotency_key=f'key-{request.pk}',
            amount=Decimal(amount), status=PaymentTransaction.SUCCESS,
            completed_at=when,
        )

    def test_six_buckets_ending_in_the_current_month(self):
        rows = totals_by_month(PaymentRequest.objects.all(), today=TODAY)

        self.assertEqual([r['month'] for r in rows],
                         ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10'])

    def test_requests_are_bucketed_by_their_own_date(self):
        self.make_request('24500.00', date(2026, 8, 11), invoice='INV-A')
        self.make_request('67000.00', date(2026, 10, 2), invoice='INV-B')
        self.make_request('100.00', date(2026, 4, 30), invoice='INV-OLD')  # before the window

        rows = {r['month']: r for r in totals_by_month(PaymentRequest.objects.all(), today=TODAY)}

        self.assertEqual(rows['2026-08']['count'], 1)
        self.assertEqual(rows['2026-08']['total'], '24500.00')
        self.assertEqual(rows['2026-10']['count'], 1)
        self.assertEqual(rows['2026-10']['total'], '67000.00')
        self.assertEqual(rows['2026-09']['count'], 0)
        self.assertEqual(rows['2026-09']['total'], '0.00')

    def test_paid_uses_the_successful_payment_in_kenyan_time(self):
        august = self.make_request('24500.00', date(2026, 8, 11), invoice='INV-A')
        # 23:00 UTC on 31 August is 02:00 on 1 September in Nairobi.
        self.pay(august, '24500.00', datetime(2026, 8, 31, 23, 0, tzinfo=timezone.utc))

        rows = {r['month']: r for r in totals_by_month(PaymentRequest.objects.all(), today=TODAY)}

        self.assertEqual(rows['2026-08']['paid'], '0.00')
        self.assertEqual(rows['2026-09']['paid'], '24500.00')
        self.assertEqual(rows['2026-09']['paid_count'], 1)

    def test_failed_attempts_never_count_as_paid(self):
        request = self.make_request('900.00', date(2026, 10, 1), status=PaymentRequest.FAILED)
        PaymentTransaction.objects.create(
            request=request, idempotency_key='nope', amount=Decimal('900.00'),
            status=PaymentTransaction.FAILED, completed_at=datetime(2026, 10, 2, 9, 0, tzinfo=EAT),
        )

        rows = {r['month']: r for r in totals_by_month(PaymentRequest.objects.all(), today=TODAY)}

        self.assertEqual(rows['2026-10']['paid'], '0.00')

    def test_scope_still_applies(self):
        self.make_request('1000.00', date(2026, 10, 1), invoice='INV-A')
        self.make_request('2000.00', date(2026, 10, 2), invoice='INV-B')

        rows = totals_by_month(PaymentRequest.objects.filter(invoice_number='INV-A'), today=TODAY)

        self.assertEqual(rows[-1]['total'], '1000.00')

    def test_empty_queryset_gives_zeroes(self):
        rows = totals_by_month(PaymentRequest.objects.none(), today=TODAY)

        self.assertEqual(len(rows), 6)
        self.assertTrue(all(r['count'] == 0 and r['total'] == '0.00' for r in rows))
        self.assertTrue(all(r['paid_count'] == 0 and r['paid'] == '0.00' for r in rows))

    def test_summary_includes_the_series(self):
        self.make_request('500.00', date(2026, 10, 1))

        report = summary(PaymentRequest.objects.all())

        self.assertIn('by_month', report)
        self.assertEqual(len(report['by_month']), 6)
