import uuid
import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [("branches", "0001_initial"), ("organizations", "0001_initial")]
    operations = [
        migrations.CreateModel(name="Ingredient", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("name", models.CharField(max_length=120)), ("is_allergen", models.BooleanField(default=False)),
            ("allergen_code", models.CharField(blank=True, max_length=40)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ingredients", to="organizations.organization")),
        ], options={"constraints": [models.UniqueConstraint(fields=("organization", "name"), name="unique_ingredient_name_per_org")]}),
        migrations.CreateModel(name="Menu", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("name", models.CharField(max_length=160)), ("currency", models.CharField(default="IRR", max_length=3)),
            ("is_active", models.BooleanField(default=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("branch", models.ForeignKey(blank=True, help_text="Null means organization-wide menu.", null=True, on_delete=django.db.models.deletion.CASCADE, related_name="menus", to="branches.branch")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="menus", to="organizations.organization")),
        ], options={"indexes": [models.Index(fields=["organization", "branch", "is_active"], name="menus_org_branch_active_idx")]}),
        migrations.CreateModel(name="Category", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("name", models.CharField(max_length=120)), ("description", models.TextField(blank=True)), ("sort_order", models.PositiveIntegerField(default=0)), ("is_active", models.BooleanField(default=True)),
            ("menu", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="categories", to="menus.menu")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="menu_categories", to="organizations.organization")),
        ], options={"ordering": ["sort_order", "name"], "constraints": [models.UniqueConstraint(fields=("menu", "name"), name="unique_category_name_per_menu")]}),
        migrations.CreateModel(name="MenuItem", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("name", models.CharField(max_length=160)), ("description", models.TextField(blank=True)), ("image_url", models.URLField(blank=True)),
            ("base_price", models.PositiveBigIntegerField(help_text="Integer minor units in the menu currency.")), ("discount_price", models.PositiveBigIntegerField(blank=True, null=True)),
            ("calories", models.PositiveIntegerField(blank=True, null=True)), ("weight_grams", models.PositiveIntegerField(blank=True, null=True)),
            ("preparation_minutes", models.PositiveSmallIntegerField(default=10)), ("spice_level", models.PositiveSmallIntegerField(default=0)),
            ("food_type", models.CharField(choices=[("regular", "Regular"), ("vegetarian", "Vegetarian"), ("vegan", "Vegan")], default="regular", max_length=20)),
            ("tags", models.JSONField(blank=True, default=list)), ("is_available", models.BooleanField(default=True)), ("is_active", models.BooleanField(default=True)),
            ("is_featured", models.BooleanField(default=False)), ("is_chef_recommended", models.BooleanField(default=False)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("category", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="menus.category")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="menu_items", to="organizations.organization")),
        ], options={"indexes": [models.Index(fields=["organization", "category", "is_active", "is_available"], name="menus_item_scope_idx")], "constraints": [models.CheckConstraint(condition=models.Q(("spice_level__lte", 5)), name="menu_item_spice_level_lte_five"), models.CheckConstraint(condition=models.Q(("discount_price__isnull", True), ("discount_price__lte", models.F("base_price")), _connector="OR"), name="discount_not_above_base_price")]}),
        migrations.CreateModel(name="MenuItemIngredient", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("is_removable", models.BooleanField(default=False)),
            ("ingredient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="menus.ingredient")),
            ("menu_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="menus.menuitem")),
        ], options={"constraints": [models.UniqueConstraint(fields=("menu_item", "ingredient"), name="unique_item_ingredient")]}),
        migrations.AddField(model_name="menuitem", name="ingredients", field=models.ManyToManyField(related_name="menu_items", through="menus.MenuItemIngredient", to="menus.ingredient")),
        migrations.CreateModel(name="OptionGroup", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("name", models.CharField(max_length=100)),
            ("min_selections", models.PositiveSmallIntegerField(default=0)), ("max_selections", models.PositiveSmallIntegerField(default=1)),
            ("is_required", models.BooleanField(default=False)), ("sort_order", models.PositiveIntegerField(default=0)),
            ("menu_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="option_groups", to="menus.menuitem")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="option_groups", to="organizations.organization")),
        ], options={"constraints": [models.CheckConstraint(condition=models.Q(("max_selections__gte", models.F("min_selections"))), name="option_max_gte_min")]}),
        migrations.CreateModel(name="Option", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("name", models.CharField(max_length=100)),
            ("price_delta", models.BigIntegerField(default=0)), ("is_available", models.BooleanField(default=True)), ("sort_order", models.PositiveIntegerField(default=0)),
            ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="options", to="menus.optiongroup")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="options", to="organizations.organization")),
        ]),
        migrations.CreateModel(name="AddOn", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("name", models.CharField(max_length=100)),
            ("price", models.PositiveBigIntegerField(default=0)), ("max_quantity", models.PositiveSmallIntegerField(default=1)), ("is_available", models.BooleanField(default=True)),
            ("menu_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="add_ons", to="menus.menuitem")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="add_ons", to="organizations.organization")),
        ], options={"constraints": [models.CheckConstraint(condition=models.Q(("max_quantity__gte", 1)), name="addon_quantity_at_least_one")]}),
        migrations.CreateModel(name="BranchItemAvailability", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("is_available", models.BooleanField(default=True)), ("stock_quantity", models.PositiveIntegerField(blank=True, null=True)),
            ("price_override", models.PositiveBigIntegerField(blank=True, null=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="item_availability", to="branches.branch")),
            ("menu_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="branch_availability", to="menus.menuitem")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="branch_item_availability", to="organizations.organization")),
        ], options={"indexes": [models.Index(fields=["organization", "branch", "is_available"], name="menus_avail_scope_idx")], "constraints": [models.UniqueConstraint(fields=("branch", "menu_item"), name="unique_branch_item_availability")]}),
    ]
