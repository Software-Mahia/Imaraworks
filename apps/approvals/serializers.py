from rest_framework import serializers

from apps.payment_requests.serializers import PaymentRequestSerializer

from .services import approval_summary


class QueueItemSerializer(PaymentRequestSerializer):
    """A payment request plus its ``approval`` block.

    Extends Part A's serializer instead of listing fields again, so a queue item
    always has the same fields as GET /api/payment-requests/<id>/.
    """

    approval = serializers.SerializerMethodField()

    def get_approval(self, obj):
        return approval_summary(obj)
