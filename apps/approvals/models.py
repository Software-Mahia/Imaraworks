from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q

from apps.approvals.logic import LEVEL_FINANCE, LEVEL_MANAGER
from apps.payment_requests.models import PaymentRequest

# Module-level so Meta below can use it: Meta can't see names defined in the
# Approval class body.
_APPROVED = 'APPROVED'


class Approval(models.Model):
    """One approve or reject action by one approver on one payment request.

    Rows are never deleted or edited after the fact. When an amount change
    invalidates earlier approvals, they are marked ``superseded`` instead, so
    the history of who approved what (and at which amount) is kept.
    """

    APPROVED = _APPROVED
    REJECTED = 'REJECTED'
    DECISION_CHOICES = [
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
    ]

    # Levels reuse the constants the approval rules use, so the rules and the
    # stored data can never disagree on spelling.
    LEVEL_CHOICES = [
        (LEVEL_MANAGER, 'Manager'),
        (LEVEL_FINANCE, 'Finance'),
    ]

    request = models.ForeignKey(PaymentRequest, on_delete=models.PROTECT, related_name='approvals')
    approver = models.ForeignKey(User, on_delete=models.PROTECT, related_name='approvals_given')
    decision = models.CharField(max_length=10, choices=DECISION_CHOICES)
    # Stored on the row, not worked out later from the approver's role, so a
    # role change afterwards can't rewrite history.
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    reason = models.TextField(blank=True)
    superseded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        constraints = [
            # Backstop for "no double approval": at most one approval that
            # still counts per level per request. The service checks this
            # first; the database catches two approvers clicking at once.
            models.UniqueConstraint(
                fields=['request', 'level'],
                condition=Q(decision=_APPROVED, superseded=False),
                name='one_active_approval_per_level',
            ),
            # Backstop for "rejections must include a reason".
            models.CheckConstraint(
                condition=Q(decision=_APPROVED) | ~Q(reason=''),
                name='rejection_requires_reason',
            ),
        ]

    def __str__(self):
        return f"{self.get_decision_display()} by {self.approver.username} ({self.level}) on #{self.request_id}"
