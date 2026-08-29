import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [("branches", "0001_initial"), ("menus", "0001_initial"), ("orders", "0004_order_fulfillment_promotions"), ("organizations", "0001_initial"), ("tables", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="Campaign", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("name", models.CharField(max_length=160)), ("code", models.CharField(max_length=40)), ("kind", models.CharField(choices=[("percent", "Percent"), ("fixed", "Fixed")], max_length=12)), ("value", models.PositiveBigIntegerField()), ("minimum_order", models.PositiveBigIntegerField(default=0)), ("maximum_discount", models.PositiveBigIntegerField(blank=True, null=True)), ("usage_limit", models.PositiveIntegerField(blank=True, null=True)), ("starts_at", models.DateTimeField()), ("ends_at", models.DateTimeField()), ("is_active", models.BooleanField(default=True)),
            ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="campaigns", to="branches.branch")), ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="campaigns", to="organizations.organization")),
        ], options={"constraints": [models.UniqueConstraint(fields=("organization", "code"), name="unique_campaign_code_org")]}),
        migrations.CreateModel(name="MenuSchedule", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("weekdays", models.JSONField(default=list)), ("starts_at", models.TimeField()), ("ends_at", models.TimeField()), ("is_active", models.BooleanField(default=True)),
            ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="menu_schedules", to="branches.branch")), ("menu", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="schedules", to="menus.menu")), ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="menu_schedules", to="organizations.organization")),
        ]),
        migrations.CreateModel(name="StockItem", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("unit", models.CharField(default="gram", max_length=20)), ("quantity", models.DecimalField(decimal_places=3, default=0, max_digits=14)), ("reorder_level", models.DecimalField(decimal_places=3, default=0, max_digits=14)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stock_items", to="branches.branch")), ("ingredient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_items", to="menus.ingredient")), ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stock_items", to="organizations.organization")),
        ], options={"constraints": [models.UniqueConstraint(fields=("branch", "ingredient"), name="unique_branch_ingredient_stock")]}),
        migrations.CreateModel(name="Reservation", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("guest_name", models.CharField(max_length=120)), ("guest_phone", models.CharField(max_length=30)), ("party_size", models.PositiveSmallIntegerField()), ("starts_at", models.DateTimeField()), ("duration_minutes", models.PositiveSmallIntegerField(default=90)), ("status", models.CharField(choices=[("pending", "Pending"), ("confirmed", "Confirmed"), ("seated", "Seated"), ("cancelled", "Cancelled"), ("no_show", "No show")], default="pending", max_length=16)), ("note", models.CharField(blank=True, max_length=300)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reservations", to="branches.branch")), ("customer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reservations", to=settings.AUTH_USER_MODEL)), ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reservations", to="organizations.organization")), ("table", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reservations", to="tables.restauranttable")),
        ], options={"indexes": [models.Index(fields=["organization", "branch", "starts_at", "status"], name="reservation_scope_time_idx")]}),
        migrations.CreateModel(name="RecipeComponent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("quantity", models.DecimalField(decimal_places=3, max_digits=12)), ("menu_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recipe_components", to="menus.menuitem")), ("stock_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recipe_components", to="operations.stockitem")),
        ], options={"constraints": [models.UniqueConstraint(fields=("menu_item", "stock_item"), name="unique_recipe_stock_component")]}),
        migrations.CreateModel(name="StockMovement", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("delta", models.DecimalField(decimal_places=3, max_digits=14)), ("reason", models.CharField(max_length=60)), ("created_at", models.DateTimeField(auto_now_add=True)), ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)), ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_movements", to="orders.order")), ("stock_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="movements", to="operations.stockitem")),
        ]),
        migrations.CreateModel(name="CampaignRedemption", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("discount_amount", models.PositiveBigIntegerField()), ("created_at", models.DateTimeField(auto_now_add=True)), ("campaign", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="redemptions", to="operations.campaign")), ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="campaign_redemption", to="orders.order")),
        ]),
    ]
