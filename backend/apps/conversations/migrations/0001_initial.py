import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [("branches", "0001_initial"), ("customers", "0001_initial"), ("identity", "0001_initial"), ("organizations", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="Conversation", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("status", models.CharField(choices=[("active", "Active"), ("archived", "Archived")], default="active", max_length=16)),
            ("provider", models.CharField(default="local", max_length=32)), ("model", models.CharField(blank=True, max_length=80)),
            ("expires_at", models.DateTimeField()), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conversations", to="branches.branch")),
            ("customer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ai_conversations", to=settings.AUTH_USER_MODEL)),
            ("guest", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="conversations", to="identity.guestidentity")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conversations", to="organizations.organization")),
            ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conversations", to="customers.tablesession")),
        ], options={"indexes": [models.Index(fields=["organization", "branch", "status"], name="conversation_tenant_scope_idx")], "constraints": [models.UniqueConstraint(condition=models.Q(("status", "active")), fields=("session",), name="one_active_conversation_per_session")]}),
        migrations.CreateModel(name="Message", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("role", models.CharField(choices=[("user", "User"), ("assistant", "Assistant"), ("tool", "Tool")], max_length=16)),
            ("content", models.TextField(blank=True)), ("tool_name", models.CharField(blank=True, max_length=80)), ("metadata", models.JSONField(blank=True, default=dict)),
            ("input_tokens", models.PositiveIntegerField(default=0)), ("output_tokens", models.PositiveIntegerField(default=0)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="conversations.conversation")),
        ], options={"ordering": ["created_at"], "indexes": [models.Index(fields=["conversation", "created_at"], name="conversation_message_time_idx")]}),
    ]
