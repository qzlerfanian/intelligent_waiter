import hashlib
import uuid
from django.db import models
from apps.branches.models import Branch
from apps.organizations.models import Organization

class TableStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    OCCUPIED = "occupied", "Occupied"
    RESERVED = "reserved", "Reserved"
    OUT_OF_SERVICE = "out_of_service", "Out of service"

class RestaurantTable(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="tables")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="tables")
    number = models.CharField(max_length=32)
    capacity = models.PositiveSmallIntegerField(default=2)
    status = models.CharField(max_length=32, choices=TableStatus.choices, default=TableStatus.AVAILABLE)
    is_active = models.BooleanField(default=True)
    qr_token_hash = models.CharField(max_length=64, unique=True, editable=False)
    qr_rotated_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["branch", "number"], name="unique_table_number_per_branch"),
            models.CheckConstraint(condition=models.Q(capacity__gte=1), name="table_capacity_at_least_one"),
        ]
        indexes = [models.Index(fields=["organization", "branch", "is_active"], name="tables_org_branch_active_idx")]

    @staticmethod
    def hash_token(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
