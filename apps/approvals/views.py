"""HTTP endpoints for approvals. See docs/API.md.

These views only translate: HTTP in, a services.py call, HTTP out. Every
approval rule lives in logic.py / services.py (golden rule 2).
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import get_role
from apps.payment_requests.serializers import PaymentRequestSerializer
from apps.payment_requests.views import visible_requests

from . import logic
from .serializers import AmountChangeSerializer
from .services import (
    MSG_ALREADY_SUBMITTED,
    MSG_AMOUNT_LOCKED,
    MSG_NOT_REQUESTER,
    MSG_NOT_REQUESTER_EDIT,
    MSG_REASON_REQUIRED,
    AmountChangeDenied,
    ApprovalDenied,
    SubmitDenied,
    approval_queue,
    approval_summary,
    approve,
    change_amount,
    reject,
    submit,
)

# Which HTTP status each refusal becomes:
#   403 "not you"          -- the user can never do this
#   409 "not now"          -- the request's state changed; reload it
#   400 "fix your input"
DENIAL_STATUS = {
    logic.MSG_ROLE_CANNOT: status.HTTP_403_FORBIDDEN,
    logic.MSG_NOT_PENDING: status.HTTP_409_CONFLICT,
    logic.MSG_SELF_APPROVAL: status.HTTP_403_FORBIDDEN,
    logic.MSG_NOT_REQUIRED: status.HTTP_403_FORBIDDEN,
    logic.MSG_ALREADY_APPROVED: status.HTTP_409_CONFLICT,
    MSG_REASON_REQUIRED: status.HTTP_400_BAD_REQUEST,
    MSG_NOT_REQUESTER: status.HTTP_403_FORBIDDEN,
    MSG_ALREADY_SUBMITTED: status.HTTP_409_CONFLICT,
    MSG_NOT_REQUESTER_EDIT: status.HTTP_403_FORBIDDEN,
    MSG_AMOUNT_LOCKED: status.HTTP_409_CONFLICT,
}


def denied_response(exc):
    return Response({"detail": exc.reason}, status=DENIAL_STATUS[exc.reason])


class IsApprover(BasePermission):
    message = logic.MSG_ROLE_CANNOT

    def has_permission(self, request, view):
        return logic.approver_level(get_role(request.user)) is not None


class ApprovalQueueView(APIView):
    permission_classes = [IsAuthenticated, IsApprover]

    def get(self, request):
        items = approval_queue(request.user)
        return Response(PaymentRequestSerializer(items, many=True).data)


class ApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        # 404 first: a request you can't see doesn't exist as far as you know.
        payment_request = get_object_or_404(visible_requests(request.user), pk=pk)
        try:
            approve(payment_request, request.user)
        except ApprovalDenied as exc:
            return denied_response(exc)
        payment_request.refresh_from_db()
        return Response({
            "id": payment_request.id,
            "status": payment_request.status,
            "approval": approval_summary(payment_request),
        })


class RejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        payment_request = get_object_or_404(visible_requests(request.user), pk=pk)
        reason = request.data.get("reason")
        if not isinstance(reason, str):
            reason = None   # a number or list is treated as no reason
        try:
            decision = reject(payment_request, request.user, reason)
        except ApprovalDenied as exc:
            return denied_response(exc)
        payment_request.refresh_from_db()
        return Response({
            "id": payment_request.id,
            "status": payment_request.status,
            "reason": decision.reason,
            "approval": approval_summary(payment_request),
        })


class SubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        # 404 first, as for approve: you can't submit what you can't see.
        payment_request = get_object_or_404(visible_requests(request.user), pk=pk)
        try:
            submit(payment_request, request.user)
        except SubmitDenied as exc:
            return denied_response(exc)
        payment_request.refresh_from_db()
        # The full request plus its approval block (asked for on PR #5), so the
        # page can update the row without fetching it again.
        return Response(PaymentRequestSerializer(payment_request).data)


class AmountChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        payment_request = get_object_or_404(visible_requests(request.user), pk=pk)
        # The body is checked before the rules: a malformed amount is a 400
        # whoever sends it, and saying so reveals nothing about the request.
        body = AmountChangeSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            change_amount(payment_request, request.user, body.validated_data["amount"])
        except AmountChangeDenied as exc:
            return denied_response(exc)
        payment_request.refresh_from_db()
        # Same response as submit: the full request plus its approval block.
        return Response(PaymentRequestSerializer(payment_request).data)
