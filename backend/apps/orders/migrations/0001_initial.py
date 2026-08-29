import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [("branches", "0001_initial"), ("customers", "0001_initial"), ("identity", "0001_initial"), ("menus", "0001_initial"), ("organizations", "0001_initial"), ("tables", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="Cart", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("currency", models.CharField(default="IRR", max_length=3)), ("status", models.CharField(choices=[("active", "Active"), ("converted", "Converted"), ("abandoned", "Abandoned")], default="active", max_length=16)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="carts", to="branches.branch")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="carts", to="organizations.organization")),
            ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="carts", to="customers.tablesession")),
        ], options={"indexes": [models.Index(fields=["organization", "branch", "status"], name="orders_cart_scope_idx")], "constraints": [models.UniqueConstraint(condition=models.Q(("status", "active")), fields=("session",), name="one_active_cart_per_session")]}),
        migrations.CreateModel(name="CartLine", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("quantity", models.PositiveSmallIntegerField(default=1)),
            ("unit_price", models.PositiveBigIntegerField()), ("note", models.CharField(blank=True, max_length=500)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("cart", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="orders.cart")),
            ("menu_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cart_lines", to="menus.menuitem")),
        ], options={"constraints": [models.CheckConstraint(condition=models.Q(("quantity__gte", 1)), name="cart_line_quantity_at_least_one")]}),
        migrations.CreateModel(name="CartLineOption", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("price_delta", models.BigIntegerField(default=0)),
            ("line", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="selected_options", to="orders.cartline")),
            ("option", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="menus.option")),
        ], options={"constraints": [models.UniqueConstraint(fields=("line", "option"), name="unique_cart_line_option")]}),
        migrations.CreateModel(name="CartLineAddOn", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("quantity", models.PositiveSmallIntegerField(default=1)), ("unit_price", models.PositiveBigIntegerField()),
            ("add_on", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="menus.addon")),
            ("line", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="selected_add_ons", to="orders.cartline")),
        ], options={"constraints": [models.UniqueConstraint(fields=("line", "add_on"), name="unique_cart_line_addon"), models.CheckConstraint(condition=models.Q(("quantity__gte", 1)), name="cart_addon_quantity_at_least_one")]}),
        migrations.CreateModel(name="Order", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("status", models.CharField(choices=[("pending", "Pending"), ("confirmed", "Confirmed"), ("preparing", "Preparing"), ("ready", "Ready"), ("completed", "Completed"), ("cancelled", "Cancelled")], default="pending", max_length=16)),
            ("currency", models.CharField(default="IRR", max_length=3)), ("subtotal", models.PositiveBigIntegerField()), ("total", models.PositiveBigIntegerField()),
            ("idempotency_key", models.CharField(max_length=128)), ("version", models.PositiveIntegerField(default=1)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="branches.branch")),
            ("customer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="customer_orders", to=settings.AUTH_USER_MODEL)),
            ("guest", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="orders", to="identity.guestidentity")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="organizations.organization")),
            ("session", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="customers.tablesession")),
            ("table", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="tables.restauranttable")),
        ], options={"indexes": [models.Index(fields=["organization", "branch", "status", "created_at"], name="orders_order_scope_idx")], "constraints": [models.UniqueConstraint(fields=("organization", "idempotency_key"), name="unique_order_idempotency_per_org")]}),
        migrations.CreateModel(name="OrderLine", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("item_name", models.CharField(max_length=160)),
            ("quantity", models.PositiveSmallIntegerField()), ("unit_price", models.PositiveBigIntegerField()), ("options", models.JSONField(default=list)), ("add_ons", models.JSONField(default=list)),
            ("note", models.CharField(blank=True, max_length=500)), ("line_total", models.PositiveBigIntegerField()),
            ("menu_item", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_lines", to="menus.menuitem")),
            ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="orders.order")),
        ], options={"constraints": [models.CheckConstraint(condition=models.Q(("quantity__gte", 1)), name="order_line_quantity_at_least_one")]}),
    ]
