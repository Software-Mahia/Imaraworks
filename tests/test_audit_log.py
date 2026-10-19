"""Database tests for the AuditLog model (apps/audit/models.py).

The rule under test: the audit log is append-only. Entries can be written and
read, but never edited or deleted through the model.
"""

import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import ProtectedError
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.payment_requests.models import PaymentRequest, Project
from apps.vendors.models import Vendor


class AuditLogTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user('alice')
        cls.carol = User.objects.create_user('carol')
        cls.request = PaymentRequest.objects.create(
            vendor=Vendor.objects.create(name='Nairobi Cement Ltd', service='Cement'),
            project=Project.objects.create(name='Kilimani Apartments'),
            requester=cls.alice,
            amount=Decimal('24500'),
            reason='Cement for phase 1',
            invoice_number='INV-001',
            payment_method=PaymentRequest.MPESA,
            date=datetime.date(2026, 10, 14),
        )

    def _log(self, action=AuditLog.APPROVED, **details):
        return AuditLog.objects.create(request=self.request, actor=self.carol,
                                       action=action, details=details)

    def test_entry_is_recorded_with_details(self):
        entry = self._log(level='manager', amount='24500')
        entry.refresh_from_db()
        self.assertEqual(entry.actor, self.carol)
        self.assertEqual(entry.action, AuditLog.APPROVED)
        self.assertEqual(entry.details, {'level': 'manager', 'amount': '24500'})
        self.assertIsNotNone(entry.timestamp)

    def test_details_default_to_empty(self):
        entry = AuditLog.objects.create(request=self.request, actor=self.alice,
                                        action=AuditLog.CREATED)
        self.assertEqual(entry.details, {})

    def test_entries_come_back_in_time_order(self):
        first = self._log(AuditLog.CREATED)
        second = self._log(AuditLog.SUBMITTED)
        self.assertEqual(list(self.request.audit_logs.all()), [first, second])

    # --- Append-only ---
    def test_entry_cannot_be_edited(self):
        entry = self._log()
        entry.action = AuditLog.REJECTED
        with self.assertRaises(ValueError):
            entry.save()
        entry.refresh_from_db()
        self.assertEqual(entry.action, AuditLog.APPROVED)

    def test_entry_cannot_be_deleted(self):
        entry = self._log()
        with self.assertRaises(ValueError):
            entry.delete()
        self.assertTrue(AuditLog.objects.filter(pk=entry.pk).exists())

    # Bulk queryset calls skip the model's save()/delete(), so they need their own guard.
    def _querysets(self, entry):
        """Both ways code reaches the log: the model's manager and a request's related manager."""
        return [
            ('AuditLog.objects', AuditLog.objects.filter(pk=entry.pk)),
            ('request.audit_logs', self.request.audit_logs.all()),
        ]

    def test_entries_cannot_be_bulk_updated(self):
        entry = self._log()
        for via, qs in self._querysets(entry):
            with self.subTest(via=via), self.assertRaises(ValueError):
                qs.update(action=AuditLog.PAID)
        entry.refresh_from_db()
        self.assertEqual(entry.action, AuditLog.APPROVED)

    def test_entries_cannot_be_bulk_updated_with_bulk_update(self):
        entry = self._log()
        entry.action = AuditLog.PAID
        # bulk_update runs inside its own atomic block, so the error breaks the
        # surrounding transaction. A savepoint lets the test keep querying.
        with self.assertRaises(ValueError), transaction.atomic():
            AuditLog.objects.bulk_update([entry], ['action'])
        entry.refresh_from_db()
        self.assertEqual(entry.action, AuditLog.APPROVED)

    def test_entries_cannot_be_bulk_deleted(self):
        entry = self._log()
        for via, qs in self._querysets(entry):
            with self.subTest(via=via), self.assertRaises(ValueError):
                qs.delete()
        self.assertTrue(AuditLog.objects.filter(pk=entry.pk).exists())

    def test_request_with_history_cannot_be_deleted(self):
        self._log()
        with self.assertRaises(ProtectedError):
            self.request.delete()
