from django.shortcuts import render
from django.contrib.auth.models import User
from django.db.models import QuerySet
from rest_framework import generics
from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS


from apps.accounts.models import Profile
from apps.accounts.permissions import get_role

from .models import PaymentRequest
from .serializers import PaymentRequestSerializer

CAN_CREATE: tuple[str, ...] = (Profile.EMPLOYEE, Profile.MANAGER, Profile.FINANCE)
CAN_SEE_ALL: tuple[str, ...] = (Profile.MANAGER, Profile.FINANCE)

class CanCreatePaymentRequest(BasePermission):
    message = "Your role cannot create payment requests."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return get_role(request.user) in CAN_CREATE

def visible_requests(user: User) -> QuerySet[PaymentRequest]:
    qs = PaymentRequest.objects.select_related('vendor', 'project', 'requester').order_by('-created_at')
    role = get_role(user)
    if role in CAN_SEE_ALL:
        return qs
    if role == Profile.EMPLOYEE:
        return qs.filter(requester=user)
    return qs.none()


class PaymentRequestListCreate(generics.ListCreateAPIView):
    serializer_class = PaymentRequestSerializer
    permission_classes = [IsAuthenticated, CanCreatePaymentRequest]

    def get_queryset(self):
        return visible_requests(self.request.user)

    def perform_create(self, serializer):
        serializer.save(requester=self.request.user)


class PaymentRequestDetail(generics.RetrieveAPIView):
    serializer_class = PaymentRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[PaymentRequest]:
        return visible_requests(self.request.user)
