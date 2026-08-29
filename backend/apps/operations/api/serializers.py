from rest_framework import serializers
from decimal import Decimal
from apps.operations.models import Campaign, MenuSchedule, RecipeComponent, Reservation, StockItem, StockMovement
from shared.tenancy.scopes import accessible_branch_ids

class ScopedSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        organization = self.context["request"].organization
        for value in attrs.values():
            if hasattr(value, "organization_id") and value.organization_id != organization.id:
                raise serializers.ValidationError("Related objects must belong to the selected organization.")
        def value(name):
            return attrs.get(name, getattr(self.instance, name, None))
        branch = value("branch")
        stock = value("stock_item")
        if stock is not None:
            branch = stock.branch
        ids = accessible_branch_ids(self.context["request"].user, organization)
        if ids is not None and (branch is None or branch.id not in ids):
            raise serializers.ValidationError("You can only manage your assigned branches.")
        menu = value("menu")
        item = value("menu_item")
        if item is not None:
            menu = item.category.menu
        if menu is not None and menu.branch_id is not None and (branch is None or menu.branch_id != branch.id):
            raise serializers.ValidationError("The menu and resource must use the same branch.")
        table = value("table")
        if table is not None and (branch is None or table.branch_id != branch.id):
            raise serializers.ValidationError({"table": "Table must belong to the selected branch."})
        start, end = value("starts_at"), value("ends_at")
        if start is not None and end is not None and end <= start:
            raise serializers.ValidationError({"ends_at": "End must be after start."})
        return attrs

class CampaignSerializer(ScopedSerializer):
    class Meta:
        model = Campaign
        fields = ["id", "branch", "name", "code", "kind", "value", "minimum_order", "maximum_discount", "usage_limit", "starts_at", "ends_at", "is_active"]
        read_only_fields = ["id"]
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get("kind", getattr(self.instance, "kind", None)) == Campaign.Kind.PERCENT and attrs.get("value", getattr(self.instance, "value", 0)) > 100:
            raise serializers.ValidationError({"value": "Percentage cannot exceed 100."})
        return attrs

class MenuScheduleSerializer(ScopedSerializer):
    class Meta:
        model = MenuSchedule
        fields = ["id", "branch", "menu", "weekdays", "starts_at", "ends_at", "is_active"]
        read_only_fields = ["id"]
    def validate_weekdays(self, value):
        if not value or any(not isinstance(day, int) or day < 0 or day > 6 for day in value):
            raise serializers.ValidationError("Weekdays must contain integers from 0 to 6.")
        return sorted(set(value))

class StockItemSerializer(ScopedSerializer):
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0"), required=False)
    reorder_level = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0"), required=False)
    low_stock = serializers.SerializerMethodField()
    class Meta:
        model = StockItem
        fields = ["id", "branch", "ingredient", "unit", "quantity", "reorder_level", "low_stock", "updated_at"]
        read_only_fields = ["id", "updated_at", "low_stock"]
    def get_low_stock(self, obj): return obj.quantity <= obj.reorder_level
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance and "quantity" in attrs and attrs["quantity"] != self.instance.quantity:
            raise serializers.ValidationError({"quantity": "Use the stock adjustment action to record a reason and audit trail."})
        return attrs

class RecipeComponentSerializer(ScopedSerializer):
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    class Meta:
        model = RecipeComponent
        fields = ["id", "menu_item", "stock_item", "quantity"]
        read_only_fields = ["id"]

class StockAdjustmentSerializer(serializers.Serializer):
    delta = serializers.DecimalField(max_digits=14, decimal_places=3)
    reason = serializers.CharField(max_length=60)
    def validate_delta(self, value):
        if value == 0: raise serializers.ValidationError("Delta cannot be zero.")
        return value

class ReservationSerializer(ScopedSerializer):
    party_size = serializers.IntegerField(min_value=1, max_value=30)
    duration_minutes = serializers.IntegerField(min_value=30, max_value=240, required=False)
    class Meta:
        model = Reservation
        fields = ["id", "branch", "table", "customer", "guest_name", "guest_phone", "party_size", "starts_at", "duration_minutes", "status", "note", "created_at"]
        read_only_fields = ["id", "customer", "created_at"]

class CustomerReservationSerializer(serializers.Serializer):
    guest_name = serializers.CharField(max_length=120)
    guest_phone = serializers.CharField(max_length=30)
    party_size = serializers.IntegerField(min_value=1, max_value=30)
    starts_at = serializers.DateTimeField()
    duration_minutes = serializers.IntegerField(min_value=30, max_value=240, default=90)
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
