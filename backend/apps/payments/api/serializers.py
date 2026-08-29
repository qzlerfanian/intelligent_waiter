from rest_framework import serializers

from apps.payments.models import Invoice, PaymentAttempt


class CreatePaymentSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    method = serializers.ChoiceField(choices=PaymentAttempt.Method.choices)


class PaymentSerializer(serializers.ModelSerializer):
    checkout = serializers.SerializerMethodField()
    class Meta:
        model = PaymentAttempt
        fields = ["id", "order", "method", "status", "amount", "currency", "provider", "provider_reference", "checkout", "created_at", "paid_at"]
    def get_checkout(self, obj):
        if obj.method != PaymentAttempt.Method.ONLINE or obj.status != PaymentAttempt.Status.PENDING:
            return None
        return {"provider": "mock_gateway", "confirm_path": f"/api/v1/customer/payments/{obj.id}/mock-confirm/", "token": str(obj.gateway_token)}


class InvoiceSerializer(serializers.ModelSerializer):
    order_id = serializers.UUIDField(source="order.id")
    payment_id = serializers.UUIDField(source="payment.id")
    class Meta:
        model = Invoice
        fields = ["id", "number", "order_id", "payment_id", "currency", "subtotal", "total", "issued_at"]


class MockConfirmSerializer(serializers.Serializer):
    token = serializers.UUIDField()

