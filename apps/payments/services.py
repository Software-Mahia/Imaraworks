"""Payment orchestration service.

Handles idempotency, locking, and transaction boundaries. The gateway is called
OUTSIDE the database transaction to avoid holding locks during external calls.
"""
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.payment_requests.models import PaymentRequest
from apps.payments.gateways import ChargeResult, PaymentGateway, get_gateway
from apps.payments.models import PaymentTransaction


class PaymentDenied(Exception):
    """Raised when a payment cannot be initiated."""
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# Statuses that can transition to payment processing
PAYABLE_STATUSES = {PaymentRequest.APPROVED}


@dataclass(frozen=True)
class PaymentResult:
    """Result of a payment initiation."""
    transaction: PaymentTransaction
    replayed: bool  # True if this was a replay of an existing key
    charge_result: ChargeResult | None = None


def initiate_payment(
    *,
    payment_request: PaymentRequest,
    idempotency_key: str,
    gateway_name: str = "mock",
    amount: Decimal | None = None,
    currency: str = "KES",
    description: str = "",
) -> PaymentResult:
    """Initiate payment for an approved request.

    Idempotency:
    - If `idempotency_key` already exists for this request, return the existing
      transaction (replayed=True) without calling the gateway again.
    - If a different key is used for the same request, the DB constraint
      `one_successful_payment_per_request` prevents double SUCCESS.

    Concurrency:
    - The request row is locked with `select_for_update` while checking status
      and creating the PROCESSING transaction.
    - The gateway is called OUTSIDE the transaction to avoid holding locks.
    - A second transaction updates the result.

    Args:
        payment_request: The approved payment request.
        idempotency_key: Client-provided unique key (e.g., UUID). Must be unique per request.
        gateway_name: Registered gateway name (default: "mock").
        amount: Override amount (defaults to request.amount).
        currency: ISO currency code (default: "KES").
        description: Description sent to gateway (can contain "FAIL" to trigger mock decline).

    Returns:
        PaymentResult with transaction, replayed flag, and charge result.

    Raises:
        PaymentDenied: If request is not payable, already paid, or key conflicts.
    """
    # --- Step 1: Lock request, check idempotency key FIRST, then status, create PROCESSING transaction ---
    with transaction.atomic():
        locked_request = PaymentRequest.objects.select_for_update().get(pk=payment_request.pk)

        # Check for existing idempotency key on THIS request (BEFORE status check)
        existing = PaymentTransaction.objects.filter(
            request=locked_request,
            idempotency_key=idempotency_key,
        ).first()
        if existing:
            # Replay: return existing transaction, don't call gateway again
            return PaymentResult(transaction=existing, replayed=True)

        # Check if already successfully paid (BEFORE status check - status might be PAID)
        if locked_request.payment_transactions.filter(status=PaymentTransaction.SUCCESS).exists():
            raise PaymentDenied("Request has already been paid successfully")

        # Check for in-flight payment (PROCESSING) to prevent concurrent attempts
        if locked_request.payment_transactions.filter(status=PaymentTransaction.PROCESSING).exists():
            raise PaymentDenied("A payment is already being processed for this request")

        if locked_request.status not in PAYABLE_STATUSES:
            raise PaymentDenied(f"Request is not payable (status: {locked_request.status})")

        # Use request amount if not overridden
        charge_amount = amount if amount is not None else locked_request.amount

        # Create PROCESSING transaction
        txn = PaymentTransaction.objects.create(
            request=locked_request,
            idempotency_key=idempotency_key,
            amount=charge_amount,
            currency=currency,
            status=PaymentTransaction.PROCESSING,
            gateway=gateway_name,
        )

        # Update request status to PROCESSING
        locked_request.status = PaymentRequest.PROCESSING
        locked_request.save(update_fields=["status", "updated_at"])

    # --- Step 2: Call gateway OUTSIDE the transaction ---
    gateway: PaymentGateway = get_gateway(gateway_name)
    charge_result = gateway.charge(
        amount=charge_amount,
        currency=currency,
        reference=str(txn.pk),
        description=description or f"Request #{locked_request.pk} - {locked_request.vendor.name} - {locked_request.reason}",
        idempotency_key=idempotency_key,
    )

    # --- Step 3: Update transaction with result in a new transaction ---
    with transaction.atomic():
        # Re-lock the transaction row
        txn = PaymentTransaction.objects.select_for_update().get(pk=txn.pk)

        if charge_result.status == "SUCCESS":
            txn.status = PaymentTransaction.SUCCESS
            txn.provider_reference = charge_result.reference
            txn.completed_at = timezone.now()

            # Update request to PAID
            locked_request = PaymentRequest.objects.select_for_update().get(pk=locked_request.pk)
            locked_request.status = PaymentRequest.PAID
            locked_request.save(update_fields=["status", "updated_at"])

        else:
            txn.status = PaymentTransaction.FAILED
            txn.provider_reason = charge_result.reason or "Provider declined"
            txn.completed_at = timezone.now()

            # Request goes back to APPROVED so it can be retried
            locked_request = PaymentRequest.objects.select_for_update().get(pk=locked_request.pk)
            locked_request.status = PaymentRequest.APPROVED
            locked_request.save(update_fields=["status", "updated_at"])

        txn.save(update_fields=["status", "provider_reference", "provider_reason", "completed_at", "updated_at"])

    return PaymentResult(transaction=txn, replayed=False, charge_result=charge_result)
