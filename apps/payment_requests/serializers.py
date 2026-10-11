from rest_framework import serializers
from .models import PaymentRequest


class PaymentRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentRequest
        fields = '__all__'

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate_invoice_number(self, value):
        if not value.strip():
            raise serializers.ValidationError("Invoice number is required.")
        return value

    def validate_vendor(self, value):
        if not value.is_active:
            raise serializers.ValidationError("This vendor is no longer active.")
        return value