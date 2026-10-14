"""Payment API views."""
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Profile
from apps.payment_requests.models import PaymentRequest
from apps.payments.models import PaymentTransaction
from apps.payments.services import PaymentDenied, initiate_payment


def _get_role(user):
    """Return the user's role string, or None if they have no profile."""
    profile = getattr(user, "profile", None)
    return profile.role if profile else None


class IsFinance(IsAuthenticated):
    """Permission: only FINANCE role."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return _get_role(request.user) == Profile.FINANCE


@api_view(["POST"])
@permission_classes([IsFinance])
def pay_payment_request(request: Request, pk: int) -> Response:
    """Initiate payment for an approved payment request.

    Body (all optional):
    {
        "idempotency_key": "uuid-v4",        # generated if omitted
        "amount": "75000.00",                # defaults to request amount
        "currency": "KES",                   # defaults to KES
        "gateway": "mock",                   # defaults to mock
        "description": "..."                 # sent to gateway; "FAIL" triggers mock decline
    }

    Returns:
    - 200: Payment initiated (or replayed)
    - 403: Not Finance role
    - 404: Request not found or not visible
    - 409: Request not payable / already paid / idempotency key mismatch
    - 422: Validation error
    """
    try:
        payment_request = PaymentRequest.objects.select_related("vendor").get(pk=pk)
    except PaymentRequest.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    # Finance can see all requests (per Part A visibility rules)
    # No additional filtering needed

    # Idempotency key: client provides or we generate one
    idempotency_key = request.data.get("idempotency_key") or str(uuid4())

    # Optional overrides
    amount = request.data.get("amount")
    if amount is not None:
        try:
            amount = Decimal(str(amount))
        except (InvalidOperation, ValueError):
            return Response({"detail": "Invalid amount."}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    currency = request.data.get("currency", "KES")
    gateway = request.data.get("gateway", "mock")
    description = request.data.get("description", "")

    try:
        result = initiate_payment(
            payment_request=payment_request,
            idempotency_key=idempotency_key,
            gateway_name=gateway,
            amount=amount,
            currency=currency,
            description=description,
        )
    except PaymentDenied as e:
        return Response({"detail": e.reason}, status=status.HTTP_409_CONFLICT)
    except KeyError as e:
        return Response({"detail": str(e)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    txn = result.transaction
    response_data = {
        "id": txn.pk,
        "request": txn.request_id,
        "status": txn.status,
        "amount": str(txn.amount),
        "currency": txn.currency,
        "provider_reference": txn.provider_reference,
        "provider_reason": txn.provider_reason,
        "replayed": result.replayed,
        "created_at": txn.created_at,
        "completed_at": txn.completed_at,
    }

    http_status = status.HTTP_200_OK if result.replayed else status.HTTP_201_CREATED
    return Response(response_data, status=http_status)


@api_view(["GET"])
@permission_classes([IsFinance])
def payment_transaction_list(request: Request) -> Response:
    """List payment transactions (Finance only)."""
    transactions = PaymentTransaction.objects.select_related(
        "request", "request__vendor", "request__project", "request__requester"
    ).order_by("-created_at")

    data = [
        {
            "id": txn.pk,
            "request": txn.request_id,
            "request_vendor": txn.request.vendor.name if txn.request.vendor_id else None,
            "request_amount": str(txn.request.amount),
            "status": txn.status,
            "amount": str(txn.amount),
            "currency": txn.currency,
            "provider_reference": txn.provider_reference,
            "provider_reason": txn.provider_reason,
            "gateway": txn.gateway,
            "created_at": txn.created_at,
            "completed_at": txn.completed_at,
        }
        for txn in transactions
    ]
    return Response(data)
