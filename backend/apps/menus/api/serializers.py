from rest_framework import serializers
from apps.menus.models import AddOn, BranchItemAvailability, Category, Ingredient, Menu, MenuItem, MenuItemIngredient, Option, OptionGroup

class TenantRelationMixin:
    tenant_relation_fields = ()
    def validate(self, attrs):
        organization = self.context["request"].organization
        for field in self.tenant_relation_fields:
            value = attrs.get(field)
            if value is not None and value.organization_id != organization.id:
                raise serializers.ValidationError({field: "Object does not belong to the selected organization."})
        return super().validate(attrs)

class MenuSerializer(TenantRelationMixin, serializers.ModelSerializer):
    tenant_relation_fields = ("branch",)
    class Meta:
        model = Menu
        fields = ["id", "branch", "name", "currency", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]

class CategorySerializer(TenantRelationMixin, serializers.ModelSerializer):
    tenant_relation_fields = ("menu",)
    class Meta:
        model = Category
        fields = ["id", "menu", "name", "description", "sort_order", "is_active"]
        read_only_fields = ["id"]

class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ["id", "name", "is_allergen", "allergen_code"]
        read_only_fields = ["id"]

class MenuItemIngredientSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="ingredient.name", read_only=True)
    is_allergen = serializers.BooleanField(source="ingredient.is_allergen", read_only=True)
    allergen_code = serializers.CharField(source="ingredient.allergen_code", read_only=True)
    class Meta:
        model = MenuItemIngredient
        fields = ["ingredient", "name", "is_allergen", "allergen_code", "is_removable"]

class OptionSerializer(TenantRelationMixin, serializers.ModelSerializer):
    tenant_relation_fields = ("group",)
    class Meta:
        model = Option
        fields = ["id", "group", "name", "price_delta", "is_available", "sort_order"]
        read_only_fields = ["id"]

class OptionGroupSerializer(TenantRelationMixin, serializers.ModelSerializer):
    tenant_relation_fields = ("menu_item",)
    options = OptionSerializer(many=True, read_only=True)
    class Meta:
        model = OptionGroup
        fields = ["id", "menu_item", "name", "min_selections", "max_selections", "is_required", "sort_order", "options"]
        read_only_fields = ["id"]
    def validate(self, attrs):
        attrs = super().validate(attrs)
        minimum = attrs.get("min_selections", getattr(self.instance, "min_selections", 0))
        maximum = attrs.get("max_selections", getattr(self.instance, "max_selections", 1))
        if maximum < minimum:
            raise serializers.ValidationError("max_selections must be greater than or equal to min_selections.")
        return attrs

class AddOnSerializer(TenantRelationMixin, serializers.ModelSerializer):
    tenant_relation_fields = ("menu_item",)
    class Meta:
        model = AddOn
        fields = ["id", "menu_item", "name", "price", "max_quantity", "is_available"]
        read_only_fields = ["id"]
    def validate_max_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Maximum quantity must be at least one.")
        return value

class MenuItemSerializer(TenantRelationMixin, serializers.ModelSerializer):
    tenant_relation_fields = ("category",)
    ingredient_links = MenuItemIngredientSerializer(source="menuitemingredient_set", many=True, read_only=True)
    option_groups = OptionGroupSerializer(many=True, read_only=True)
    add_ons = AddOnSerializer(many=True, read_only=True)
    ingredient_ids = serializers.PrimaryKeyRelatedField(source="ingredients", queryset=Ingredient.objects.all(), many=True, write_only=True, required=False)
    class Meta:
        model = MenuItem
        fields = ["id", "category", "name", "description", "image_url", "base_price", "discount_price", "calories", "weight_grams", "preparation_minutes", "spice_level", "food_type", "tags", "is_available", "is_active", "is_featured", "is_chef_recommended", "ingredient_ids", "ingredient_links", "option_groups", "add_ons", "created_at"]
        read_only_fields = ["id", "created_at"]
    def validate_ingredient_ids(self, ingredients):
        organization = self.context["request"].organization
        if any(item.organization_id != organization.id for item in ingredients):
            raise serializers.ValidationError("Every ingredient must belong to the selected organization.")
        return ingredients
    def validate(self, attrs):
        attrs = super().validate(attrs)
        base = attrs.get("base_price", getattr(self.instance, "base_price", None))
        discount = attrs.get("discount_price", getattr(self.instance, "discount_price", None))
        if discount is not None and base is not None and discount > base:
            raise serializers.ValidationError({"discount_price": "Discount price cannot exceed base price."})
        if attrs.get("spice_level", getattr(self.instance, "spice_level", 0)) > 5:
            raise serializers.ValidationError({"spice_level": "Spice level must be between 0 and 5."})
        return attrs

class AvailabilitySerializer(TenantRelationMixin, serializers.ModelSerializer):
    tenant_relation_fields = ("branch", "menu_item")
    class Meta:
        model = BranchItemAvailability
        fields = ["id", "branch", "menu_item", "is_available", "stock_quantity", "price_override", "updated_at"]
        read_only_fields = ["id", "updated_at"]
    def validate(self, attrs):
        attrs = super().validate(attrs)
        branch = attrs.get("branch", getattr(self.instance, "branch", None))
        item = attrs.get("menu_item", getattr(self.instance, "menu_item", None))
        if branch and item:
            menu_branch_id = item.category.menu.branch_id
            if menu_branch_id is not None and menu_branch_id != branch.id:
                raise serializers.ValidationError("A branch-specific item can only be overridden by its own branch.")
        return attrs

class PublicMenuItemSerializer(MenuItemSerializer):
    effective_price = serializers.SerializerMethodField()
    effective_availability = serializers.SerializerMethodField()
    class Meta(MenuItemSerializer.Meta):
        fields = MenuItemSerializer.Meta.fields + ["effective_price", "effective_availability"]
    def get_effective_price(self, obj):
        override = next((entry for entry in obj.branch_availability.all() if entry.branch_id == self.context["branch"].id), None)
        return override.price_override if override and override.price_override is not None else (obj.discount_price if obj.discount_price is not None else obj.base_price)
    def get_effective_availability(self, obj):
        override = next((entry for entry in obj.branch_availability.all() if entry.branch_id == self.context["branch"].id), None)
        return obj.is_active and obj.is_available and (override is None or (override.is_available and (override.stock_quantity is None or override.stock_quantity > 0)))

class PublicCategorySerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    class Meta:
        model = Category
        fields = ["id", "name", "description", "sort_order", "items"]
    def get_items(self, obj):
        return PublicMenuItemSerializer(obj.items.filter(is_active=True), many=True, context=self.context).data

class PublicMenuSerializer(serializers.ModelSerializer):
    categories = PublicCategorySerializer(many=True, read_only=True)
    class Meta:
        model = Menu
        fields = ["id", "name", "currency", "categories"]
