import uuid
from django.db import models
from apps.branches.models import Branch
from apps.customers.models import TableSession
from apps.identity.models import GuestIdentity, User
from apps.organizations.models import Organization

class Conversation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="conversations")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="conversations")
    session = models.ForeignKey(TableSession, on_delete=models.CASCADE, related_name="conversations")
    guest = models.ForeignKey(GuestIdentity, null=True, blank=True, on_delete=models.SET_NULL, related_name="conversations")
    customer = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="ai_conversations")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    provider = models.CharField(max_length=32, default="local")
    model = models.CharField(max_length=80, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["session"], condition=models.Q(status="active"), name="one_active_conversation_per_session")]
        indexes = [models.Index(fields=["organization", "branch", "status"], name="conversation_tenant_scope_idx")]

class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        TOOL = "tool", "Tool"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField(blank=True)
    tool_name = models.CharField(max_length=80, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "created_at"], name="conversation_message_time_idx")]
