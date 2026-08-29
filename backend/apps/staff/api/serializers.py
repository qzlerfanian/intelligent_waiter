from rest_framework import serializers
from apps.orders.models import Order, OrderLine, OrderStatusEvent

class StaffOrderLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderLine
        fields = ["id", "item_name", "quantity", "options", "add_ons", "note", "line_total"]

class StatusEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.display_name", read_only=True, default="System")
    class Meta:
        model = OrderStatusEvent
        fields = ["id", "from_status", "to_status", "actor_name", "reason", "created_at"]

class StaffOrderSerializer(serializers.ModelSerializer):
    lines = StaffOrderLineSerializer(many=True)
    table_number = serializers.CharField(source="table.number")
    branch_name = serializers.CharField(source="branch.name")
    history = StatusEventSerializer(source="status_events", many=True, read_only=True)
    payment = serializers.SerializerMethodField()
    class Meta:
        model = Order
        fields = ["id", "branch", "branch_name", "table_number", "status", "currency", "subtotal", "discount_total", "total", "promotion_code", "fulfillment_type", "delivery_address", "payment", "version", "lines", "history", "created_at", "updated_at"]
    def get_payment(self, obj):
        from apps.payments.services import order_payment_summary
        return order_payment_summary(obj)

class TransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)
    version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")

class CollectPaymentSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=["cash", "pos"])
