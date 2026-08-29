import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [("organizations", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="Branch", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("name", models.CharField(max_length=200)),
            ("code", models.SlugField(max_length=64)),
            ("address", models.TextField(blank=True)),
            ("timezone", models.CharField(default="Asia/Tehran", max_length=64)),
            ("is_active", models.BooleanField(default=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="branches", to="organizations.organization")),
        ], options={"indexes": [models.Index(fields=["organization", "is_active"], name="branches_br_organiz_a0d65b_idx")], "constraints": [models.UniqueConstraint(fields=("organization", "code"), name="unique_branch_code_per_org")]}),
        migrations.CreateModel(name="BranchAssignment", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignments", to="branches.branch")),
            ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="branch_assignments", to=settings.AUTH_USER_MODEL)),
        ], options={"constraints": [models.UniqueConstraint(fields=("branch", "user"), name="unique_branch_assignment")]}),
    ]
