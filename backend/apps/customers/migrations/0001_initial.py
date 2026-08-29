import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [("branches", "0001_initial"), ("identity", "0001_initial"), ("organizations", "0001_initial"), ("tables", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="TableSession", fields=[
        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
        ("token_hash", models.CharField(editable=False, max_length=64, unique=True)),
        ("status", models.CharField(choices=[("active", "Active"), ("closed", "Closed"), ("expired", "Expired")], default="active", max_length=16)),
        ("expires_at", models.DateTimeField()), ("created_at", models.DateTimeField(auto_now_add=True)), ("last_seen_at", models.DateTimeField(auto_now=True)),
        ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="table_sessions", to="branches.branch")),
        ("customer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="table_sessions", to=settings.AUTH_USER_MODEL)),
        ("guest", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="table_sessions", to="identity.guestidentity")),
        ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="table_sessions", to="organizations.organization")),
        ("table", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sessions", to="tables.restauranttable")),
    ], options={"indexes": [models.Index(fields=["token_hash", "status"], name="customers_token_status_idx"), models.Index(fields=["organization", "branch", "status"], name="customers_org_branch_idx")]})]
