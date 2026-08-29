import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("branches", "0001_initial"), ("orders", "0001_initial"), ("organizations", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="OrderStatusEvent", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("from_status", models.CharField(blank=True, max_length=16)),
            ("to_status", models.CharField(choices=[("pending", "Pending"), ("confirmed", "Confirmed"), ("preparing", "Preparing"), ("ready", "Ready"), ("completed", "Completed"), ("cancelled", "Cancelled")], max_length=16)),
            ("reason", models.CharField(blank=True, max_length=300)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_status_events", to=settings.AUTH_USER_MODEL)),
            ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_events", to="branches.branch")),
            ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="status_events", to="orders.order")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_events", to="organizations.organization")),
        ], options={"indexes": [models.Index(fields=["organization", "branch", "created_at"], name="orders_event_scope_idx")]}),
        migrations.CreateModel(name="NotificationOutbox", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("topic", models.CharField(max_length=80)), ("payload", models.JSONField(default=dict)),
            ("status", models.CharField(choices=[("pending", "Pending"), ("processed", "Processed"), ("failed", "Failed")], default="pending", max_length=16)),
            ("attempts", models.PositiveSmallIntegerField(default=0)), ("available_at", models.DateTimeField(auto_now_add=True)),
            ("processed_at", models.DateTimeField(blank=True, null=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notification_outbox", to="branches.branch")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notification_outbox", to="organizations.organization")),
        ], options={"indexes": [models.Index(fields=["status", "available_at"], name="orders_outbox_pending_idx"), models.Index(fields=["organization", "branch", "created_at"], name="orders_outbox_scope_idx")]}),
    ]
