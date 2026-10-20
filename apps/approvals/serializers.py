from decimal import Decimal

from rest_framework import serializers


class AmountChangeSerializer(serializers.Serializer):
    """Body of PATCH /api/payment-requests/<id>/amount/: just the new amount.

    Same field limits as PaymentRequest.amount (12 digits, 2 decimal places)
    and the same "greater than zero" rule and message as Part A's create
    serializer, so an amount valid on create is valid on edit and vice versa.
    """

    amount = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate_amount(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value
