import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("customers", "0001_initial"), ("menus", "0001_initial"), ("orders", "0003_order_confirmation"), ("organizations", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="CustomerProfile", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("diet", models.CharField(choices=[("none", "No restriction"), ("vegetarian", "Vegetarian"), ("vegan", "Vegan")], default="none", max_length=20)),
            ("allergen_codes", models.JSONField(default=list)), ("disliked_ingredients", models.JSONField(default=list)), ("spice_preference", models.PositiveSmallIntegerField(blank=True, null=True)),
            ("ai_personalization_consent", models.BooleanField(default=False)), ("retention_consent", models.BooleanField(default=False)), ("marketing_consent", models.BooleanField(default=False)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("customer", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="customer_profile", to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="Favorite", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="favorites", to=settings.AUTH_USER_MODEL)),
            ("menu_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="favorited_by", to="menus.menuitem")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="customer_favorites", to="organizations.organization")),
        ], options={"constraints": [models.UniqueConstraint(fields=("organization", "customer", "menu_item"), name="unique_customer_favorite_org")]}),
        migrations.CreateModel(name="LoyaltyAccount", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("points_balance", models.PositiveIntegerField(default=0)), ("lifetime_points", models.PositiveIntegerField(default=0)), ("tier", models.CharField(default="bronze", max_length=20)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="loyalty_accounts", to=settings.AUTH_USER_MODEL)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="loyalty_accounts", to="organizations.organization")),
        ], options={"constraints": [models.UniqueConstraint(fields=("organization", "customer"), name="unique_loyalty_account_org")]}),
        migrations.CreateModel(name="LoyaltyEntry", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("points", models.IntegerField()), ("reason", models.CharField(max_length=80)), ("idempotency_key", models.CharField(max_length=128)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="entries", to="customers.loyaltyaccount")),
            ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="loyalty_entries", to="orders.order")),
        ], options={"constraints": [models.UniqueConstraint(fields=("account", "idempotency_key"), name="unique_loyalty_entry_key")]}),
        migrations.CreateModel(name="ReorderAction", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("idempotency_key", models.CharField(max_length=128)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reorder_actions", to=settings.AUTH_USER_MODEL)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reorder_actions", to="organizations.organization")),
            ("source_order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reorder_actions", to="orders.order")),
        ], options={"constraints": [models.UniqueConstraint(fields=("organization", "customer", "idempotency_key"), name="unique_customer_reorder_key")]}),
        migrations.CreateModel(name="PrivacyRequest", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("scope", models.CharField(default="personalization", max_length=40)), ("status", models.CharField(choices=[("completed", "Completed")], default="completed", max_length=20)), ("created_at", models.DateTimeField(auto_now_add=True)), ("completed_at", models.DateTimeField(auto_now_add=True)),
            ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="privacy_requests", to=settings.AUTH_USER_MODEL)),
        ]),
    ]
