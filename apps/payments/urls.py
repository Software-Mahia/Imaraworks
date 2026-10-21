"""Payment API URLs."""
from django.urls import path

from .views import pay_payment_request, payment_transaction_list

# Included at api/, like the approvals URLs: pay sits next to approve, reject,
# submit and amount under /api/payment-requests/<id>/ (#33).
urlpatterns = [
    path("payment-requests/<int:pk>/pay/", pay_payment_request, name="pay-payment-request"),
    path("payments/transactions/", payment_transaction_list, name="payment-transaction-list"),
]
