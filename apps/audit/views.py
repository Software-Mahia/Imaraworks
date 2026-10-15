"""Read-only audit endpoints. See docs/APPROVALS_API.md.

Who can read what (decided with the team, see #2):
  - a request's history: exactly the people who can see that request
  - the whole log:       ADMIN only, without `details` (admins see no payment data)
There are no write endpoints: entries are only ever created by the services
that change a request's state.
"""

from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import BasePermission, IsAuthenticated

from apps.accounts.models import Profile
from apps.approvals.services import role_of
from apps.approvals.visibility import visible_requests

from .models import AuditLog
from .serializers import AuditEntrySerializer, AuditLogSerializer


class IsAdminRole(BasePermission):
    message = "Only admins can read the audit log."

    def has_permission(self, request, view):
        return role_of(request.user) == Profile.ADMIN


class RequestHistoryView(generics.ListAPIView):
    """GET /api/payment-requests/<id>/history/ -- oldest first."""

    serializer_class = AuditEntrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # 404 if the user can't see the request, the same as viewing it.
        payment_request = get_object_or_404(visible_requests(self.request.user), pk=self.kwargs['pk'])
        return payment_request.audit_logs.select_related('actor').order_by('timestamp', 'id')


class AuditLogView(generics.ListAPIView):
    """GET /api/audit/ -- whole log, newest first, optional ?action= filter."""

    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        qs = AuditLog.objects.select_related('actor').order_by('-timestamp', '-id')
        action = self.request.query_params.get('action')
        if action:
            qs = qs.filter(action=action)
        return qs
