import uuid
from django.conf import settings
from django.db import models

class Role(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Administrator"
    BRANCH_MANAGER = "branch_manager", "Branch manager"
    CASHIER = "cashier", "Cashier"
    WAITER = "waiter", "Waiter"
    CHEF = "chef", "Chef"
    KITCHEN_STAFF = "kitchen_staff", "Kitchen staff"

class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Membership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=32, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "user"], name="unique_organization_member")]
        indexes = [models.Index(fields=["user", "is_active"], name="organizati_user_id_14ef55_idx"), models.Index(fields=["organization", "role"], name="organizati_organiz_1cbc34_idx")]
