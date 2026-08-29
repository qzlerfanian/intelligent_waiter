import hashlib
import uuid
from django.db import models
from apps.branches.models import Branch
from apps.identity.models import GuestIdentity, User
from apps.organizations.models import Organization
from apps.tables.models import RestaurantTable
from apps.menus.models import MenuItem

class TableSession(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="table_sessions")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="table_sessions")
    table = models.ForeignKey(RestaurantTable, on_delete=models.PROTECT, related_name="sessions")
    guest = models.ForeignKey(GuestIdentity, null=True, blank=True, on_delete=models.SET_NULL, related_name="table_sessions")
    customer = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="table_sessions")
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["token_hash", "status"], name="customers_token_status_idx"), models.Index(fields=["organization", "branch", "status"], name="customers_org_branch_idx")]

    @staticmethod
    def hash_token(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


class CustomerProfile(models.Model):
    class Diet(models.TextChoices):
        NONE = "none", "No restriction"
        VEGETARIAN = "vegetarian", "Vegetarian"
        VEGAN = "vegan", "Vegan"

    customer = models.OneToOneField(User, on_delete=models.CASCADE, related_name="customer_profile")
    diet = models.CharField(max_length=20, choices=Diet.choices, default=Diet.NONE)
    allergen_codes = models.JSONField(default=list)
    disliked_ingredients = models.JSONField(default=list)
    spice_preference = models.PositiveSmallIntegerField(null=True, blank=True)
    ai_personalization_consent = models.BooleanField(default=False)
    retention_consent = models.BooleanField(default=False)
    marketing_consent = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)


class Favorite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="customer_favorites")
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="favorites")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "customer", "menu_item"], name="unique_customer_favorite_org")]


class LoyaltyAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="loyalty_accounts")
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="loyalty_accounts")
    points_balance = models.PositiveIntegerField(default=0)
    lifetime_points = models.PositiveIntegerField(default=0)
    tier = models.CharField(max_length=20, default="bronze")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "customer"], name="unique_loyalty_account_org")]


class LoyaltyEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(LoyaltyAccount, on_delete=models.CASCADE, related_name="entries")
    order = models.ForeignKey("orders.Order", null=True, blank=True, on_delete=models.SET_NULL, related_name="loyalty_entries")
    points = models.IntegerField()
    reason = models.CharField(max_length=80)
    idempotency_key = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["account", "idempotency_key"], name="unique_loyalty_entry_key")]


class ReorderAction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="reorder_actions")
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reorder_actions")
    source_order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="reorder_actions")
    idempotency_key = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "customer", "idempotency_key"], name="unique_customer_reorder_key")]


class PrivacyRequest(models.Model):
    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="privacy_requests")
    scope = models.CharField(max_length=40, default="personalization")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(auto_now_add=True)
