import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.branches.models import Branch, BranchAssignment
from apps.menus.models import BranchItemAvailability, Category, Menu, MenuItem
from apps.organizations.models import Membership, Organization, Role
from apps.tables.models import RestaurantTable
from apps.tables.services import issue_qr_token

User = get_user_model()

def authorized_client(user, organization):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}", HTTP_X_ORGANIZATION_ID=str(organization.id))
    return client

def tenant(role=Role.ADMIN):
    user = User.objects.create_user(email=f"{role}@example.com", password="password1234")
    organization = Organization.objects.create(name="Cafe", slug=f"cafe-{role}")
    Membership.objects.create(user=user, organization=organization, role=role)
    branch = Branch.objects.create(organization=organization, name="Main", code="main")
    return user, organization, branch

@pytest.mark.django_db
def test_table_creation_returns_raw_qr_once_and_stores_only_hash():
    user, organization, branch = tenant()
    response = authorized_client(user, organization).post("/api/v1/tables/", {"branch": str(branch.id), "number": "12", "capacity": 4})
    assert response.status_code == 201
    raw_token = response.json()["qr_token"]
    table = RestaurantTable.objects.get(id=response.json()["id"])
    assert raw_token != table.qr_token_hash
    assert RestaurantTable.hash_token(raw_token) == table.qr_token_hash

@pytest.mark.django_db
def test_invalid_qr_does_not_leak_table_data(client):
    response = client.get("/api/v1/tables/resolve/not-a-real-token/")
    assert response.status_code == 404

@pytest.mark.django_db
def test_cross_tenant_branch_is_rejected_when_creating_table():
    user, organization, _ = tenant()
    other = Organization.objects.create(name="Other", slug="other")
    foreign_branch = Branch.objects.create(organization=other, name="Foreign", code="foreign")
    response = authorized_client(user, organization).post("/api/v1/tables/", {"branch": str(foreign_branch.id), "number": "1"})
    assert response.status_code == 400

@pytest.mark.django_db
def test_public_menu_uses_branch_price_and_stock():
    _, organization, branch = tenant()
    token, token_hash = issue_qr_token()
    RestaurantTable.objects.create(organization=organization, branch=branch, number="1", qr_token_hash=token_hash)
    menu = Menu.objects.create(organization=organization, name="Shared")
    category = Category.objects.create(organization=organization, menu=menu, name="Pizza")
    item = MenuItem.objects.create(organization=organization, category=category, name="Margherita", base_price=350000)
    BranchItemAvailability.objects.create(organization=organization, branch=branch, menu_item=item, price_override=330000, stock_quantity=2)
    response = APIClient().get(f"/api/v1/menus/public/{token}/")
    assert response.status_code == 200
    public_item = response.json()["data"]["menus"][0]["categories"][0]["items"][0]
    assert public_item["effective_price"] == 330000
    assert public_item["effective_availability"] is True

@pytest.mark.django_db
def test_branch_manager_cannot_manage_unassigned_branch():
    user, organization, assigned = tenant(Role.BRANCH_MANAGER)
    BranchAssignment.objects.create(user=user, branch=assigned)
    other = Branch.objects.create(organization=organization, name="Other", code="other")
    response = authorized_client(user, organization).post("/api/v1/menus/catalogs/", {"branch": str(other.id), "name": "Forbidden", "currency": "IRR"})
    assert response.status_code == 403

@pytest.mark.django_db
def test_menu_item_rejects_ingredient_from_another_tenant():
    user, organization, branch = tenant()
    menu = Menu.objects.create(organization=organization, branch=branch, name="Main")
    category = Category.objects.create(organization=organization, menu=menu, name="Food")
    other = Organization.objects.create(name="Other", slug="ingredient-other")
    from apps.menus.models import Ingredient
    foreign_ingredient = Ingredient.objects.create(organization=other, name="Secret")
    response = authorized_client(user, organization).post("/api/v1/menus/items/", {"category": str(category.id), "name": "Dish", "base_price": 1000, "ingredient_ids": [str(foreign_ingredient.id)]})
    assert response.status_code == 400
