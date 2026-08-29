import uuid
from django.db import models
from apps.branches.models import Branch
from apps.identity.models import User
from apps.menus.models import Ingredient, Menu, MenuItem
from apps.orders.models import Order
from apps.organizations.models import Organization
from apps.tables.models import RestaurantTable

class Campaign(models.Model):
    class Kind(models.TextChoices):
        PERCENT = "percent", "Percent"
        FIXED = "fixed", "Fixed"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="campaigns")
    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.CASCADE, related_name="campaigns")
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=40)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    value = models.PositiveBigIntegerField()
    minimum_order = models.PositiveBigIntegerField(default=0)
    maximum_discount = models.PositiveBigIntegerField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "code"], name="unique_campaign_code_org")]

class CampaignRedemption(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, related_name="redemptions")
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="campaign_redemption")
    discount_amount = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

class MenuSchedule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="menu_schedules")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="menu_schedules")
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="schedules")
    weekdays = models.JSONField(default=list)
    starts_at = models.TimeField()
    ends_at = models.TimeField()
    is_active = models.BooleanField(default=True)

class StockItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="stock_items")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="stock_items")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="stock_items")
    unit = models.CharField(max_length=20, default="gram")
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    reorder_level = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["branch", "ingredient"], name="unique_branch_ingredient_stock")]

class RecipeComponent(models.Model):
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name="recipe_components")
    stock_item = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name="recipe_components")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["menu_item", "stock_item"], name="unique_recipe_stock_component")]

class StockMovement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stock_item = models.ForeignKey(StockItem, on_delete=models.PROTECT, related_name="movements")
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.SET_NULL, related_name="stock_movements")
    delta = models.DecimalField(max_digits=14, decimal_places=3)
    reason = models.CharField(max_length=60)
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

class Reservation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        SEATED = "seated", "Seated"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No show"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="reservations")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="reservations")
    table = models.ForeignKey(RestaurantTable, null=True, blank=True, on_delete=models.SET_NULL, related_name="reservations")
    customer = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="reservations")
    guest_name = models.CharField(max_length=120)
    guest_phone = models.CharField(max_length=30)
    party_size = models.PositiveSmallIntegerField()
    starts_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(default=90)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        indexes = [models.Index(fields=["organization", "branch", "starts_at", "status"], name="reservation_scope_time_idx")]
