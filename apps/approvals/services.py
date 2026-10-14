"""Approval orchestration for Part B -- "decide, then save".

logic.py answers single questions ("may this user approve?", "is it fully
approved?"). This module combines them into one complete outcome for an
approve action: which level to record, what the request's status becomes, and
what goes in the audit log.

Why split "decide" from "save"
------------------------------
``decide_approval`` is pure: plain data in, an ``ApprovalDecision`` out, no
database, so every rule is testable without one. The thin
``approve(payment_request, user)`` wrapper then does the saving:

    with transaction.atomic():
        lock the request row (select_for_update)
        decision = decide_approval(...)       # all the rules live here
        save an Approval row at decision.level
        set request.status = decision.new_status
        write an AuditLog row from decision.audit_action / audit_details

so the wrapper holds no business rules -- it only reads and writes.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from apps.approvals.logic import (
    approver_level,
    evaluate_approval,
    is_fully_approved,
    required_levels,
)
from apps.approvals.models import Approval
from apps.audit.models import AuditLog
from apps.payment_requests.models import PaymentRequest

# Status values come straight from A's PaymentRequest so there is one source of
# truth (golden rule 1). Like Profile in logic.py, importing the model class
# only reads its constants -- no database access -- so this stays pure.
STATUS_DRAFT = PaymentRequest.DRAFT
STATUS_SUBMITTED = PaymentRequest.SUBMITTED
STATUS_PENDING = PaymentRequest.PENDING_APPROVAL
STATUS_APPROVED = PaymentRequest.APPROVED
STATUS_REJECTED = PaymentRequest.REJECTED

# Audit action names come from AuditLog, the team's one audit vocabulary.
AUDIT_APPROVED = AuditLog.APPROVED
AUDIT_REJECTED = AuditLog.REJECTED
AUDIT_AMOUNT_CHANGED = AuditLog.AMOUNT_CHANGED

MSG_REASON_REQUIRED = "A reason is required to reject a request."
MSG_AMOUNT_LOCKED = "The amount can no longer be changed for this request."


class ApprovalDenied(Exception):
    """Raised when a user may not approve. ``reason`` is a logic.MSG_* sentence.

    Why an exception rather than returning (ok, reason): inside
    transaction.atomic() an exception automatically rolls back anything already
    written, and a view can turn it into a 403 in one place.
    """

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ApprovalDecision:
    """Everything the save step needs to write. Frozen so it can't be altered
    between being decided and being saved."""

    level: str            # level the new Approval row records ("manager"/"finance")
    new_status: str       # request status after this approval
    audit_action: str
    audit_details: dict


def decide_approval(*, role, is_requester, status, amount, approved_levels):
    """Work out the result of ``role`` approving a request, or raise ApprovalDenied.

    Inputs are plain data the wrapper reads off the request and user:
      - role:            approver's Profile.role
      - is_requester:    True if the approver created the request
      - status:          the request's current status
      - amount:          the request's current amount
      - approved_levels: levels already approved (excluding superseded ones)
    """
    ok, reason = evaluate_approval(
        role=role,
        is_requester=is_requester,
        is_pending=(status == STATUS_PENDING),
        amount=amount,
        approved_levels=approved_levels,
    )
    if not ok:
        raise ApprovalDenied(reason)

    level = approver_level(role)

    # Re-check completeness *including* this new approval. A small request
    # completes on the manager's approval; a large one stays PENDING until
    # both manager and finance have approved, in either order.
    levels_after = set(approved_levels) | {level}
    fully_approved = is_fully_approved(amount, levels_after)

    return ApprovalDecision(
        level=level,
        new_status=STATUS_APPROVED if fully_approved else STATUS_PENDING,
        audit_action=AUDIT_APPROVED,
        audit_details={
            "level": level,
            "amount": str(amount),
            "fully_approved": fully_approved,
        },
    )


def _role_of(user):
    """The user's Profile role, or None if they have no profile.

    Same behaviour as get_role() in PR #2 (apps/accounts/permissions.py);
    switch to that once it is merged.
    """
    profile = getattr(user, "profile", None)
    return profile.role if profile else None


def _counting_levels(payment_request):
    """Levels whose approval still counts: approved and not superseded."""
    return set(
        payment_request.approvals
        .filter(decision=Approval.APPROVED, superseded=False)
        .values_list("level", flat=True)
    )


def approve(payment_request, user):
    """Record ``user`` approving ``payment_request``. Returns the ApprovalDecision.

    Raises ApprovalDenied (nothing written) if the rules say no.

    This is the "save" half: it reads, calls decide_approval for every rule,
    then writes. All of it runs in one transaction, so the Approval row, the
    new status and the audit entry are saved together or not at all.

    The request is re-read under a row lock (select_for_update) rather than
    trusting the object passed in. That way two approvers acting at once are
    handled one after the other, and the second one sees the first one's
    approval. The one_active_approval_per_level constraint is the final backstop.
    """
    with transaction.atomic():
        locked = PaymentRequest.objects.select_for_update().get(pk=payment_request.pk)

        decision = decide_approval(
            role=_role_of(user),
            is_requester=(locked.requester_id == user.id),
            status=locked.status,
            amount=locked.amount,
            approved_levels=_counting_levels(locked),
        )

        Approval.objects.create(
            request=locked,
            approver=user,
            decision=Approval.APPROVED,
            level=decision.level,
        )
        if locked.status != decision.new_status:
            locked.status = decision.new_status
            locked.save(update_fields=["status", "updated_at"])
        AuditLog.objects.create(
            request=locked,
            actor=user,
            action=decision.audit_action,
            details=decision.audit_details,
        )

    return decision


@dataclass(frozen=True)
class RejectionDecision:
    """Everything the save step needs to write for a reject."""

    level: str            # level the rejecting Approval row records
    reason: str           # cleaned reason, stored on the Approval row
    new_status: str
    audit_action: str
    audit_details: dict


def decide_rejection(*, role, is_requester, status, amount, approved_levels, reason):
    """Work out the result of ``role`` rejecting a request, or raise ApprovalDenied.

    Who may reject: exactly the people who could approve right now. Rejecting is
    the same decision with the opposite answer, so it goes through the same gate
    (role, pending, not self, level required, level not already approved). This
    keeps one permission rule instead of two that could drift apart.

    The permission check runs before the reason check, so a user who isn't
    allowed to reject is told that, not asked for a reason.
    """
    ok, denial = evaluate_approval(
        role=role,
        is_requester=is_requester,
        is_pending=(status == STATUS_PENDING),
        amount=amount,
        approved_levels=approved_levels,
    )
    if not ok:
        raise ApprovalDenied(denial)

    # Rule: rejections must include a reason. Whitespace-only counts as empty,
    # otherwise "   " would get past a plain truthiness check.
    cleaned = (reason or "").strip()
    if not cleaned:
        raise ApprovalDenied(MSG_REASON_REQUIRED)

    level = approver_level(role)

    # One rejection at any level ends the request, unlike approval, which
    # needs every required level.
    return RejectionDecision(
        level=level,
        reason=cleaned,
        new_status=STATUS_REJECTED,
        audit_action=AUDIT_REJECTED,
        audit_details={
            "level": level,
            "amount": str(amount),
            "reason": cleaned,
        },
    )


class AmountChangeDenied(Exception):
    """Raised when a request's amount may not be changed in its current status."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class AmountChangeDecision:
    """Everything the save step needs to write when an amount changes."""

    supersede_levels: frozenset   # mark these levels' Approval rows superseded
    new_status: str
    retiered: bool                # True if the change crossed the 50k line
    audit_action: str
    audit_details: dict


# Statuses whose amount may still be edited. DRAFT and SUBMITTED have no
# approvals yet; PENDING / APPROVED have approvals that the change will
# invalidate. Anything later (REJECTED, or in/after payment) is locked: once
# money may be moving, changing the amount would break the "never pay the
# wrong amount" guarantee.
_EDITABLE_STATUSES = {STATUS_DRAFT, STATUS_SUBMITTED, STATUS_PENDING, STATUS_APPROVED}

# Of those, the ones that come before approval: nothing to invalidate, so the
# status is left alone.
_PRE_APPROVAL_STATUSES = {STATUS_DRAFT, STATUS_SUBMITTED}


def decide_amount_change(*, status, old_amount, new_amount, approved_levels):
    """Work out the result of changing a request's amount, or raise AmountChangeDenied.

    Returns None if the amount didn't actually change (nothing to do).

    Rule: approvers approved a specific amount, so ANY change after approval
    invalidates every current approval -- even a decrease. The approvals are
    marked superseded (kept for the audit trail), not deleted, and the request
    goes back to PENDING to be approved again.

    Re-tiering needs no special code: approval always reads required_levels()
    on the CURRENT amount, so a request that now crosses 50k automatically needs
    finance too. ``retiered`` is only reported here so the audit log shows it.
    """
    old_amount = Decimal(str(old_amount))
    new_amount = Decimal(str(new_amount))
    if new_amount == old_amount:
        return None

    if status not in _EDITABLE_STATUSES:
        raise AmountChangeDenied(MSG_AMOUNT_LOCKED)

    retiered = required_levels(old_amount) != required_levels(new_amount)

    # Before approval (draft or submitted) there are no approvals to
    # invalidate, so the status stays as it is.
    if status in _PRE_APPROVAL_STATUSES:
        supersede = frozenset()
        new_status = status
    else:
        supersede = frozenset(approved_levels)
        new_status = STATUS_PENDING

    return AmountChangeDecision(
        supersede_levels=supersede,
        new_status=new_status,
        retiered=retiered,
        audit_action=AUDIT_AMOUNT_CHANGED,
        audit_details={
            "old_amount": str(old_amount),
            "new_amount": str(new_amount),
            "superseded_levels": sorted(supersede),
            "retiered": retiered,
        },
    )
