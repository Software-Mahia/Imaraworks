from django.contrib.auth.models import User
from django.db import models

from apps.payment_requests.models import PaymentRequest


class AuditLog(models.Model):
    """One recorded action on a payment request: who did what, when.

    The log is append-only. Once written, an entry can't be edited or deleted
    through the model, because a history that can be rewritten can't be trusted.
    """

    # The team's agreed action names. Every part writes one of these, so the
    # log reads the same whoever wrote the entry.
    CREATED = 'CREATED'
    SUBMITTED = 'SUBMITTED'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    AMOUNT_CHANGED = 'AMOUNT_CHANGED'
    PAYMENT_STARTED = 'PAYMENT_STARTED'
    PAID = 'PAID'
    PAYMENT_FAILED = 'PAYMENT_FAILED'
    ACTION_CHOICES = [
        (CREATED, 'Created'),
        (SUBMITTED, 'Submitted'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
        (AMOUNT_CHANGED, 'Amount changed'),
        (PAYMENT_STARTED, 'Payment started'),
        (PAID, 'Paid'),
        (PAYMENT_FAILED, 'Payment failed'),
    ]

    request = models.ForeignKey(PaymentRequest, on_delete=models.PROTECT, related_name='audit_logs')
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    # Action-specific facts, e.g. {"level": "manager", "amount": "67000"}.
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("Audit log entries can't be changed once written.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Audit log entries can't be deleted.")

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.actor.username} {self.action} #{self.request_id}"
