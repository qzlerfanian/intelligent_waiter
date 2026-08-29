from rest_framework import serializers
from apps.customers.models import CustomerProfile, Favorite, LoyaltyAccount, LoyaltyEntry, TableSession

class StartSessionSerializer(serializers.Serializer):
    qr_token = serializers.CharField(min_length=20, max_length=200)

class TableSessionSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField()
    branch = serializers.SerializerMethodField()
    table = serializers.SerializerMethodField()
    class Meta:
        model = TableSession
        fields = ["id", "organization", "branch", "table", "status", "expires_at", "created_at"]
    def get_organization(self, obj):
        return {"id": obj.organization_id, "name": obj.organization.name, "slug": obj.organization.slug}
    def get_branch(self, obj):
        return {"id": obj.branch_id, "name": obj.branch.name, "code": obj.branch.code}
    def get_table(self, obj):
        return {"id": obj.table_id, "number": obj.table.number, "capacity": obj.table.capacity}


class CustomerProfileSerializer(serializers.ModelSerializer):
    allergen_codes = serializers.ListField(child=serializers.CharField(max_length=60), max_length=30, required=False)
    disliked_ingredients = serializers.ListField(child=serializers.CharField(max_length=80), max_length=30, required=False)
    class Meta:
        model = CustomerProfile
        fields = ["diet", "allergen_codes", "disliked_ingredients", "spice_preference", "ai_personalization_consent", "retention_consent", "marketing_consent", "updated_at"]
        read_only_fields = ["updated_at"]
    def validate_allergen_codes(self, value):
        if len(value) > 30 or any(not isinstance(item, str) or len(item) > 60 for item in value):
            raise serializers.ValidationError("Provide at most 30 short allergen codes.")
        return sorted(set(item.strip().casefold() for item in value if item.strip()))
    def validate_disliked_ingredients(self, value):
        if len(value) > 30 or any(not isinstance(item, str) or len(item) > 80 for item in value):
            raise serializers.ValidationError("Provide at most 30 short ingredient names.")
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))
    def validate_spice_preference(self, value):
        if value is not None and value > 5:
            raise serializers.ValidationError("Spice preference must be between 0 and 5.")
        return value


class FavoriteSerializer(serializers.ModelSerializer):
    item_id = serializers.UUIDField(source="menu_item_id")
    name = serializers.CharField(source="menu_item.name")
    class Meta:
        model = Favorite
        fields = ["id", "item_id", "name", "created_at"]


class FavoriteInputSerializer(serializers.Serializer):
    menu_item_id = serializers.UUIDField()


class LoyaltyEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyEntry
        fields = ["id", "points", "reason", "order", "created_at"]


class LoyaltyAccountSerializer(serializers.ModelSerializer):
    entries = LoyaltyEntrySerializer(many=True)
    class Meta:
        model = LoyaltyAccount
        fields = ["points_balance", "lifetime_points", "tier", "entries", "updated_at"]


class PrivacyEraseSerializer(serializers.Serializer):
    confirmation = serializers.CharField()
    def validate_confirmation(self, value):
        if value != "DELETE MY PERSONALIZATION":
            raise serializers.ValidationError("Explicit deletion confirmation is required.")
        return value
