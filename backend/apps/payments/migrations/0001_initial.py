import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("branches", "0001_initial"), ("orders", "0003_order_confirmation"), ("organizations", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="PaymentAttempt", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("method", models.CharField(choices=[("cash", "Cash"), ("pos", "Card terminal"), ("online", "Online")], max_length=16)),
            ("status", models.CharField(choices=[("pending", "Pending"), ("paid", "Paid"), ("failed", "Failed"), ("cancelled", "Cancelled"), ("refunded", "Refunded")], default="pending", max_length=16)),
            ("amount", models.PositiveBigIntegerField()), ("currency", models.CharField(max_length=3)), ("idempotency_key", models.CharField(max_length=128)),
            ("provider", models.CharField(default="manual", max_length=40)), ("provider_reference", models.CharField(blank=True, max_length=120)),
            ("gateway_token", models.UUIDField(blank=True, null=True, unique=True)), ("failure_code", models.CharField(blank=True, max_length=80)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)), ("paid_at", models.DateTimeField(blank=True, null=True)),
            ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="branches.branch")),
            ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_payments", to=settings.AUTH_USER_MODEL)),
            ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="orders.order")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="organizations.organization")),
        ], options={"indexes": [models.Index(fields=["organization", "branch", "status", "created_at"], name="payment_scope_status_idx")], "constraints": [models.UniqueConstraint(fields=("organization", "idempotency_key"), name="unique_payment_idempotency_org"), models.UniqueConstraint(condition=models.Q(("status", "paid")), fields=("order",), name="one_paid_payment_per_order")]}),
        migrations.CreateModel(name="PaymentEvent", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("from_status", models.CharField(blank=True, max_length=16)),
            ("to_status", models.CharField(choices=[("pending", "Pending"), ("paid", "Paid"), ("failed", "Failed"), ("cancelled", "Cancelled"), ("refunded", "Refunded")], max_length=16)),
            ("source", models.CharField(max_length=32)), ("metadata", models.JSONField(default=dict)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payment_events", to=settings.AUTH_USER_MODEL)),
            ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payment_events", to="branches.branch")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payment_events", to="organizations.organization")),
            ("payment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="payments.paymentattempt")),
        ]),
        migrations.CreateModel(name="Invoice", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("number", models.CharField(max_length=40)),
            ("currency", models.CharField(max_length=3)), ("subtotal", models.PositiveBigIntegerField()), ("total", models.PositiveBigIntegerField()), ("issued_at", models.DateTimeField(auto_now_add=True)),
            ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="invoices", to="branches.branch")),
            ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="invoice", to="orders.order")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="invoices", to="organizations.organization")),
            ("payment", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="invoice", to="payments.paymentattempt")),
        ], options={"constraints": [models.UniqueConstraint(fields=("organization", "number"), name="unique_invoice_number_org")]}),
    ]
