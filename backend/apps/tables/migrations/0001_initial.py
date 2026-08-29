import uuid
import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [("branches", "0001_initial"), ("organizations", "0001_initial")]
    operations = [migrations.CreateModel(
        name="RestaurantTable",
        fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("number", models.CharField(max_length=32)),
            ("capacity", models.PositiveSmallIntegerField(default=2)),
            ("status", models.CharField(choices=[("available", "Available"), ("occupied", "Occupied"), ("reserved", "Reserved"), ("out_of_service", "Out of service")], default="available", max_length=32)),
            ("is_active", models.BooleanField(default=True)),
            ("qr_token_hash", models.CharField(editable=False, max_length=64, unique=True)),
            ("qr_rotated_at", models.DateTimeField(auto_now_add=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tables", to="branches.branch")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tables", to="organizations.organization")),
        ],
        options={
            "indexes": [models.Index(fields=["organization", "branch", "is_active"], name="tables_org_branch_active_idx")],
            "constraints": [models.UniqueConstraint(fields=("branch", "number"), name="unique_table_number_per_branch"), models.CheckConstraint(condition=models.Q(("capacity__gte", 1)), name="table_capacity_at_least_one")],
        },
    )]
