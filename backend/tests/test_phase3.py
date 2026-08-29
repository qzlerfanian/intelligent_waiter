import pytest
from rest_framework.test import APIClient
from apps.branches.models import Branch
from apps.customers.models import TableSession
from apps.menus.models import AddOn, BranchItemAvailability, Category, Menu, MenuItem, Option, OptionGroup
from apps.orders.models import Cart, Order
from apps.organizations.models import Organization
from apps.tables.models import RestaurantTable
from apps.tables.services import issue_qr_token

def restaurant():
    organization = Organization.objects.create(name="Cafe", slug="phase3-cafe")
    branch = Branch.objects.create(organization=organization, name="Main", code="main")
    qr_token, token_hash = issue_qr_token()
    table = RestaurantTable.objects.create(organization=organization, branch=branch, number="7", qr_token_hash=token_hash)
    menu = Menu.objects.create(organization=organization, branch=branch, name="Main")
    category = Category.objects.create(organization=organization, menu=menu, name="Food")
    item = MenuItem.objects.create(organization=organization, category=category, name="Pizza", base_price=1000)
    return organization, branch, table, item, qr_token

def start_session(qr_token):
    client = APIClient()
    response = client.post("/api/v1/customer/sessions/", {"qr_token": qr_token})
    assert response.status_code == 201
    client.credentials(HTTP_X_TABLE_SESSION=response.json()["data"]["token"])
    return client, response

@pytest.mark.django_db
def test_qr_starts_anonymous_table_session():
    organization, branch, table, _, qr_token = restaurant()
    _, response = start_session(qr_token)
    session = TableSession.objects.get(id=response.json()["data"]["session"]["id"])
    assert session.organization == organization
    assert session.branch == branch
    assert session.table == table
    assert session.guest is not None

@pytest.mark.django_db
def test_cart_price_is_calculated_from_database_not_client():
    _, _, _, item, qr_token = restaurant()
    client, _ = start_session(qr_token)
    response = client.post("/api/v1/customer/cart/items/", {"menu_item_id": str(item.id), "quantity": 2, "unit_price": 1})
    assert response.status_code == 201
    assert response.json()["data"]["unit_price"] == 1000
    assert response.json()["data"]["line_total"] == 2000

@pytest.mark.django_db
def test_required_option_is_enforced():
    organization, _, _, item, qr_token = restaurant()
    group = OptionGroup.objects.create(organization=organization, menu_item=item, name="Size", min_selections=1, max_selections=1, is_required=True)
    Option.objects.create(organization=organization, group=group, name="Large", price_delta=500)
    client, _ = start_session(qr_token)
    response = client.post("/api/v1/customer/cart/items/", {"menu_item_id": str(item.id), "quantity": 1})
    assert response.status_code == 400

@pytest.mark.django_db
def test_unavailable_stock_cannot_be_added():
    organization, branch, _, item, qr_token = restaurant()
    BranchItemAvailability.objects.create(organization=organization, branch=branch, menu_item=item, stock_quantity=0)
    client, _ = start_session(qr_token)
    response = client.post("/api/v1/customer/cart/items/", {"menu_item_id": str(item.id), "quantity": 1})
    assert response.status_code == 400

@pytest.mark.django_db
def test_confirm_order_snapshots_cart_and_is_idempotent():
    _, _, _, item, qr_token = restaurant()
    client, _ = start_session(qr_token)
    client.post("/api/v1/customer/cart/items/", {"menu_item_id": str(item.id), "quantity": 2})
    first = client.post("/api/v1/customer/orders/confirm/", HTTP_IDEMPOTENCY_KEY="checkout-1")
    second = client.post("/api/v1/customer/orders/confirm/", HTTP_IDEMPOTENCY_KEY="checkout-1")
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert Order.objects.count() == 1
    assert Order.objects.get().lines.get().item_name == "Pizza"
    assert Cart.objects.get().status == Cart.Status.CONVERTED

@pytest.mark.django_db
def test_session_cannot_read_another_sessions_order():
    _, _, _, item, qr_token = restaurant()
    first, _ = start_session(qr_token)
    first.post("/api/v1/customer/cart/items/", {"menu_item_id": str(item.id), "quantity": 1})
    order_id = first.post("/api/v1/customer/orders/confirm/", HTTP_IDEMPOTENCY_KEY="first-order").json()["data"]["id"]
    second, _ = start_session(qr_token)
    assert second.get(f"/api/v1/customer/orders/{order_id}/").status_code == 404
