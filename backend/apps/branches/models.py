import uuid
from django.conf import settings
from django.db import models
from apps.organizations.models import Organization

class Branch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="branches")
    name = models.CharField(max_length=200)
    code = models.SlugField(max_length=64)
    address = models.TextField(blank=True)
    timezone = models.CharField(max_length=64, default="Asia/Tehran")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "code"], name="unique_branch_code_per_org")]
        indexes = [models.Index(fields=["organization", "is_active"], name="branches_br_organiz_a0d65b_idx")]

class BranchAssignment(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="assignments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="branch_assignments")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["branch", "user"], name="unique_branch_assignment")]
