from django.urls import path

from .views import AuditLogView, RequestHistoryView

# Included at api/, like apps/approvals/urls.py.
urlpatterns = [
    path('audit/', AuditLogView.as_view(), name='audit-log'),
    path('payment-requests/<int:pk>/history/', RequestHistoryView.as_view(), name='payment-request-history'),
]
