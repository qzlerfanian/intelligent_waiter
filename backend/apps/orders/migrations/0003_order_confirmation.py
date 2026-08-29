import uuid
import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("branches", "0001_initial"), ("customers", "0001_initial"), ("orders", "0002_order_events_and_outbox"), ("organizations", "0001_initial")]
    operations = [migrations.CreateModel(name="OrderConfirmation", fields=[
        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
        ("cart_fingerprint", models.CharField(max_length=64)),
        ("status", models.CharField(choices=[("pending", "Pending"), ("confirmed", "Confirmed"), ("cancelled", "Cancelled"), ("expired", "Expired")], default="pending", max_length=16)),
        ("expires_at", models.DateTimeField()), ("created_at", models.DateTimeField(auto_now_add=True)), ("confirmed_at", models.DateTimeField(blank=True, null=True)),
        ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="order_confirmations", to="branches.branch")),
        ("cart", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="confirmations", to="orders.cart")),
        ("order", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="confirmation", to="orders.order")),
        ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="order_confirmations", to="organizations.organization")),
        ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="order_confirmations", to="customers.tablesession")),
    ], options={"indexes": [models.Index(fields=["session", "status", "expires_at"], name="order_confirmation_lookup_idx")]})]
