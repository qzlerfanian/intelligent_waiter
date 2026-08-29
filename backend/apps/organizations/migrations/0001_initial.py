import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="Organization", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("name", models.CharField(max_length=200)),
            ("slug", models.SlugField(unique=True)),
            ("is_active", models.BooleanField(default=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
        ]),
        migrations.CreateModel(name="Membership", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("role", models.CharField(choices=[("owner", "Owner"), ("admin", "Administrator"), ("branch_manager", "Branch manager"), ("cashier", "Cashier"), ("waiter", "Waiter"), ("chef", "Chef"), ("kitchen_staff", "Kitchen staff")], max_length=32)),
            ("is_active", models.BooleanField(default=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="organizations.organization")),
            ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to=settings.AUTH_USER_MODEL)),
        ], options={"indexes": [models.Index(fields=["user", "is_active"], name="organizati_user_id_14ef55_idx"), models.Index(fields=["organization", "role"], name="organizati_organiz_1cbc34_idx")], "constraints": [models.UniqueConstraint(fields=("organization", "user"), name="unique_organization_member")]}),
    ]
