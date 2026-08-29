from rest_framework import serializers
from apps.orders.models import Cart, CartLine, CartLineAddOn, CartLineOption, Order, OrderLine
from apps.orders.services import line_total

class AddOnInputSerializer(serializers.Serializer):
    add_on_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)

class AddCartLineSerializer(serializers.Serializer):
    menu_item_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=50, default=1)
    option_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    add_ons = AddOnInputSerializer(many=True, required=False, default=list)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")

    def validate_add_ons(self, value):
        ids = [entry["add_on_id"] for entry in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Each add-on may appear only once.")
        return value

class UpdateCartLineSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=50, required=False)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)

class ConfirmOrderSerializer(serializers.Serializer):
    promotion_code = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    fulfillment_type = serializers.ChoiceField(choices=Order.Fulfillment.choices, required=False, default=Order.Fulfillment.DINE_IN)
    delivery_address = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")

class CartOptionSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="option_id")
    name = serializers.CharField(source="option.name")
    class Meta:
        model = CartLineOption
        fields = ["id", "name", "price_delta"]

class CartAddOnSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="add_on_id")
    name = serializers.CharField(source="add_on.name")
    class Meta:
        model = CartLineAddOn
        fields = ["id", "name", "quantity", "unit_price"]

class CartLineSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="menu_item.name")
    options = CartOptionSerializer(source="selected_options", many=True)
    add_ons = CartAddOnSerializer(source="selected_add_ons", many=True)
    line_total = serializers.SerializerMethodField()
    class Meta:
        model = CartLine
        fields = ["id", "menu_item", "item_name", "quantity", "unit_price", "note", "options", "add_ons", "line_total"]
    def get_line_total(self, obj):
        return line_total(obj)

class CartSerializer(serializers.ModelSerializer):
    lines = CartLineSerializer(many=True)
    subtotal = serializers.SerializerMethodField()
    class Meta:
        model = Cart
        fields = ["id", "currency", "status", "lines", "subtotal", "updated_at"]
    def get_subtotal(self, obj):
        return sum(line_total(line) for line in obj.lines.all())

class OrderLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderLine
        fields = ["id", "menu_item", "item_name", "quantity", "unit_price", "options", "add_ons", "note", "line_total"]

class OrderSerializer(serializers.ModelSerializer):
    lines = OrderLineSerializer(many=True)
    table_number = serializers.CharField(source="table.number")
    payment = serializers.SerializerMethodField()
    class Meta:
        model = Order
        fields = ["id", "status", "currency", "subtotal", "discount_total", "total", "promotion_code", "fulfillment_type", "delivery_address", "table_number", "version", "payment", "lines", "created_at"]
    def get_payment(self, obj):
        from apps.payments.services import order_payment_summary
        return order_payment_summary(obj)
