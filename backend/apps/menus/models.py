import uuid
from django.db import models
from apps.branches.models import Branch
from apps.organizations.models import Organization

class Menu(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="menus")
    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.CASCADE, related_name="menus", help_text="Null means organization-wide menu.")
    name = models.CharField(max_length=160)
    currency = models.CharField(max_length=3, default="IRR")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["organization", "branch", "is_active"], name="menus_org_branch_active_idx")]

class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="menu_categories")
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["menu", "name"], name="unique_category_name_per_menu")]
        ordering = ["sort_order", "name"]

class Ingredient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="ingredients")
    name = models.CharField(max_length=120)
    is_allergen = models.BooleanField(default=False)
    allergen_code = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "name"], name="unique_ingredient_name_per_org")]

class MenuItem(models.Model):
    class FoodType(models.TextChoices):
        REGULAR = "regular", "Regular"
        VEGETARIAN = "vegetarian", "Vegetarian"
        VEGAN = "vegan", "Vegan"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="menu_items")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    base_price = models.PositiveBigIntegerField(help_text="Integer minor units in the menu currency.")
    discount_price = models.PositiveBigIntegerField(null=True, blank=True)
    calories = models.PositiveIntegerField(null=True, blank=True)
    weight_grams = models.PositiveIntegerField(null=True, blank=True)
    preparation_minutes = models.PositiveSmallIntegerField(default=10)
    spice_level = models.PositiveSmallIntegerField(default=0)
    food_type = models.CharField(max_length=20, choices=FoodType.choices, default=FoodType.REGULAR)
    tags = models.JSONField(default=list, blank=True)
    is_available = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_chef_recommended = models.BooleanField(default=False)
    ingredients = models.ManyToManyField(Ingredient, through="MenuItemIngredient", related_name="menu_items")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["organization", "category", "is_active", "is_available"], name="menus_item_scope_idx")]
        constraints = [
            models.CheckConstraint(condition=models.Q(spice_level__lte=5), name="menu_item_spice_level_lte_five"),
            models.CheckConstraint(condition=models.Q(discount_price__isnull=True) | models.Q(discount_price__lte=models.F("base_price")), name="discount_not_above_base_price"),
        ]

class MenuItemIngredient(models.Model):
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT)
    is_removable = models.BooleanField(default=False)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["menu_item", "ingredient"], name="unique_item_ingredient")]

class OptionGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="option_groups")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name="option_groups")
    name = models.CharField(max_length=100)
    min_selections = models.PositiveSmallIntegerField(default=0)
    max_selections = models.PositiveSmallIntegerField(default=1)
    is_required = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(max_selections__gte=models.F("min_selections")), name="option_max_gte_min")]

class Option(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="options")
    group = models.ForeignKey(OptionGroup, on_delete=models.CASCADE, related_name="options")
    name = models.CharField(max_length=100)
    price_delta = models.BigIntegerField(default=0)
    is_available = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

class AddOn(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="add_ons")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name="add_ons")
    name = models.CharField(max_length=100)
    price = models.PositiveBigIntegerField(default=0)
    max_quantity = models.PositiveSmallIntegerField(default=1)
    is_available = models.BooleanField(default=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(max_quantity__gte=1), name="addon_quantity_at_least_one")]

class BranchItemAvailability(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="branch_item_availability")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="item_availability")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name="branch_availability")
    is_available = models.BooleanField(default=True)
    stock_quantity = models.PositiveIntegerField(null=True, blank=True)
    price_override = models.PositiveBigIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["branch", "menu_item"], name="unique_branch_item_availability")]
        indexes = [models.Index(fields=["organization", "branch", "is_available"], name="menus_avail_scope_idx")]
