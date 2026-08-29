from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.branches.models import Branch, BranchAssignment
from apps.menus.models import Category, Ingredient, Menu, MenuItem
from apps.operations.models import MenuSchedule, StockItem, StockMovement
from apps.organizations.models import Membership, Organization
from tests.test_phase1 import client_for

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def context():
    owner = User.objects.create_user(email="manager@example.test", password="original-password")
    org = Organization.objects.create(name="Management", slug="management")
    Membership.objects.create(organization=org, user=owner, role="owner")
    branch = Branch.objects.create(organization=org, name="Main", code="main")
    return owner, org, branch, client_for(owner, org)


def test_employee_creation_assignment_update_and_removal(context):
    owner, org, branch, client = context
    response = client.post("/api/v1/organizations/members/", {
        "email": "chef@example.test", "display_name": "Chef", "password": "kitchen-private-874!",
        "role": "chef", "branches": [str(branch.id)],
    }, format="json")
    assert response.status_code == 201, response.data
    assert response.data["email"] == "chef@example.test"
    assert "password" not in response.data
    employee = User.objects.get(email="chef@example.test")
    assert employee.check_password("kitchen-private-874!")
    assert BranchAssignment.objects.filter(user=employee, branch=branch).exists()
    staff = client_for(employee, org).get("/api/v1/staff/context/")
    assert staff.status_code == 200
    assert str(branch.id) in str(staff.data)
    endpoint = f'/api/v1/organizations/members/{response.data["id"]}/'
    assert client.patch(endpoint, {"branches": [], "is_active": False}, format="json").status_code == 200
    assert not BranchAssignment.objects.filter(user=employee).exists()
    assert client_for(employee, org).get("/api/v1/staff/context/").status_code == 403
    assert client.delete(endpoint).status_code == 204
    assert User.objects.filter(pk=employee.pk).exists()


def test_employee_foreign_branch_and_existing_account_are_safe(context):
    _, org, _, client = context
    other = Organization.objects.create(name="Other", slug="other")
    foreign = Branch.objects.create(organization=other, name="Other", code="other")
    payload = {"email": "new@example.test", "password": "unrelated-strong-346!", "role": "cashier", "branches": [str(foreign.id)]}
    assert client.post("/api/v1/organizations/members/", payload, format="json").status_code == 400
    assert not User.objects.filter(email=payload["email"]).exists()
    existing = User.objects.create_user(email="existing@example.test", password="do-not-change")
    payload.update(email=existing.email, branches=[])
    assert client.post("/api/v1/organizations/members/", payload, format="json").status_code == 400
    existing.refresh_from_db()
    assert existing.check_password("do-not-change")
    response = client.post("/api/v1/organizations/members/", {"user": str(existing.id), "role": "waiter"}, format="json")
    assert response.status_code == 201, response.data
    assert Membership.objects.filter(user=existing, organization=org).exists()


def test_admin_cannot_modify_owner_or_promote_self(context):
    owner, org, _, _ = context
    admin = User.objects.create_user(email="admin@example.test")
    membership = Membership.objects.create(organization=org, user=admin, role="admin")
    client = client_for(admin, org)
    endpoint = f'/api/v1/organizations/members/{owner.memberships.get(organization=org).id}/'
    assert client.patch(endpoint, {"is_active": False}, format="json").status_code == 400
    assert client.delete(endpoint).status_code == 403
    assert client.patch(f"/api/v1/organizations/members/{membership.id}/", {"role": "owner"}, format="json").status_code == 400


def test_organization_edit_checks_target_membership(context):
    owner, org, _, client = context
    other = Organization.objects.create(name="Another", slug="another")
    Membership.objects.create(organization=other, user=owner, role="waiter")
    assert client.patch(f"/api/v1/organizations/{org.id}/", {"name": "Updated"}, format="json").status_code == 200
    assert client.patch(f"/api/v1/organizations/{other.id}/", {"name": "Not allowed"}, format="json").status_code == 403


def test_branch_manager_reads_only_assigned_branches_and_cannot_write_others(context):
    _, org, branch, _ = context
    other = Branch.objects.create(organization=org, name="Other", code="other")
    manager = User.objects.create_user(email="branch@example.test")
    Membership.objects.create(organization=org, user=manager, role="branch_manager")
    BranchAssignment.objects.create(user=manager, branch=branch)
    client = client_for(manager, org)
    response = client.get("/api/v1/organizations/branches/")
    assert response.status_code == 200
    assert [str(row["id"]) for row in response.data] == [str(branch.id)]
    assert client.post("/api/v1/organizations/branches/", {"name": "Denied", "code": "denied"}).status_code == 403
    payload = {"branch": str(other.id), "name": "Unauthorized", "code": "CODE", "kind": "percent", "value": 10, "starts_at": timezone.now().isoformat(), "ends_at": (timezone.now() + timedelta(days=1)).isoformat()}
    assert client.post("/api/v1/operations/campaigns/", payload, format="json").status_code == 400
    payload["branch"] = str(branch.id)
    response = client.post("/api/v1/operations/campaigns/", payload, format="json")
    assert response.status_code == 201, response.data
    assert client.patch(f'/api/v1/operations/campaigns/{response.data["id"]}/', {"branch": str(other.id)}, format="json").status_code == 400


def test_setup_menu_table_and_public_qr_flow(context):
    _, _, branch, client = context
    menu = client.post("/api/v1/menus/catalogs/", {"name": "Lunch", "branch": str(branch.id)}, format="json")
    assert menu.status_code == 201, menu.data
    category = client.post("/api/v1/menus/categories/", {"name": "Food", "menu": menu.data["id"]}, format="json")
    assert category.status_code == 201, category.data
    item = client.post("/api/v1/menus/items/", {"name": "Rice", "category": category.data["id"], "base_price": 100000}, format="json")
    assert item.status_code == 201, item.data
    table = client.post("/api/v1/tables/", {"branch": str(branch.id), "number": "1", "capacity": 4}, format="json")
    assert table.status_code == 201, table.data
    token = table.data["qr_token"]
    public = APIClient().get(f"/api/v1/menus/public/{token}/")
    assert public.status_code == 200, public.data
    assert public.data["data"]["menus"][0]["categories"][0]["items"][0]["name"] == "Rice"
    rotated = client.post(f'/api/v1/tables/{table.data["id"]}/rotate_qr/')
    assert rotated.status_code == 200
    assert APIClient().get(f"/api/v1/tables/resolve/{token}/").status_code == 404
    assert APIClient().get(f'/api/v1/tables/resolve/{rotated.data["data"]["qr_token"]}/').status_code == 200


def test_stock_adjustment_is_audited_and_cannot_go_negative(context):
    _, org, branch, client = context
    ingredient = Ingredient.objects.create(organization=org, name="Rice")
    response = client.post("/api/v1/operations/stock/", {"branch": str(branch.id), "ingredient": str(ingredient.id), "quantity": "10"}, format="json")
    assert response.status_code == 201, response.data
    stock = StockItem.objects.get(pk=response.data["id"])
    assert StockMovement.objects.filter(stock_item=stock, reason="initial_stock").exists()
    endpoint = f"/api/v1/operations/stock/{stock.pk}/"
    assert client.patch(endpoint, {"quantity": 20}, format="json").status_code == 400
    assert client.post(endpoint + "adjust/", {"delta": -11, "reason": "invalid"}, format="json").status_code == 400
    assert client.post(endpoint + "adjust/", {"delta": 5, "reason": "delivery"}, format="json").status_code == 200
    stock.refresh_from_db()
    assert stock.quantity == Decimal("15")
    assert StockMovement.objects.filter(stock_item=stock).count() == 2


def test_scheduled_menu_weekday_filter_on_sqlite(context):
    from apps.operations.services import active_menus
    _, org, branch, _ = context
    menu = Menu.objects.create(organization=org, branch=branch, name="Scheduled")
    now = timezone.now().replace(hour=12)
    schedule = MenuSchedule.objects.create(organization=org, branch=branch, menu=menu, weekdays=[now.weekday()], starts_at="10:00", ends_at="14:00")
    assert list(active_menus(Menu.objects.all(), branch, now)) == [menu]
    schedule.weekdays = [(now.weekday() + 1) % 7]
    schedule.save()
    assert not active_menus(Menu.objects.all(), branch, now).exists()


def test_invalid_duplicate_branch_returns_validation_error(context):
    _, _, branch, client = context
    response = client.post("/api/v1/organizations/branches/", {"name": "Duplicate", "code": branch.code}, format="json")
    assert response.status_code == 400
