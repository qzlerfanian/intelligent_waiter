from datetime import timedelta
from decimal import Decimal
import pytest
from django.utils import timezone
from apps.branches.models import Branch
from apps.customers.models import TableSession
from apps.identity.models import GuestIdentity
from apps.menus.models import Category, Ingredient, Menu, MenuItem
from apps.operations.models import Campaign, CampaignRedemption, RecipeComponent, StockItem, StockMovement
from apps.orders.models import Order
from apps.orders.services import add_cart_line, confirm_cart
from apps.organizations.models import Organization
from apps.tables.models import RestaurantTable

def phase9_context(slug="advanced-cafe"):
    org = Organization.objects.create(name="Advanced", slug=slug)
    branch = Branch.objects.create(organization=org, name="Main", code="main")
    table = RestaurantTable.objects.create(organization=org, branch=branch, number="1", qr_token_hash=(slug + "qr").ljust(64, "x"))
    guest = GuestIdentity.objects.create(expires_at=timezone.now() + timedelta(hours=3))
    session = TableSession.objects.create(organization=org, branch=branch, table=table, guest=guest, token_hash=TableSession.hash_token(slug), expires_at=timezone.now() + timedelta(hours=2))
    menu = Menu.objects.create(organization=org, branch=branch, name="Dinner")
    category = Category.objects.create(organization=org, menu=menu, name="Food")
    item = MenuItem.objects.create(organization=org, category=category, name="Burger", base_price=500000)
    return org, branch, session, item

@pytest.mark.django_db
def test_checkout_applies_scoped_campaign_and_current_inventory_atomically():
    org, branch, session, item = phase9_context()
    ingredient = Ingredient.objects.create(organization=org, name="Meat")
    stock = StockItem.objects.create(organization=org, branch=branch, ingredient=ingredient, quantity=Decimal("1000"), unit="gram")
    RecipeComponent.objects.create(menu_item=item, stock_item=stock, quantity=Decimal("150"))
    Campaign.objects.create(organization=org, branch=branch, name="Ten percent", code="SAVE10", kind="percent", value=10, starts_at=timezone.now() - timedelta(days=1), ends_at=timezone.now() + timedelta(days=1))
    add_cart_line(session=session, menu_item_id=item.id, quantity=2, option_ids=[], add_ons=[])
    order, _ = confirm_cart(session=session, idempotency_key="advanced-order", promotion_code="save10", fulfillment_type="takeaway")
    stock.refresh_from_db()
    assert order.subtotal == 1000000 and order.discount_total == 100000 and order.total == 900000
    assert order.fulfillment_type == "takeaway" and stock.quantity == Decimal("700")
    assert CampaignRedemption.objects.filter(order=order).exists() and StockMovement.objects.filter(order=order, delta=Decimal("-300")).exists()

@pytest.mark.django_db
def test_delivery_requires_address_and_foreign_campaign_is_rejected():
    org, branch, session, item = phase9_context()
    add_cart_line(session=session, menu_item_id=item.id, quantity=1, option_ids=[], add_ons=[])
    with pytest.raises(Exception):
        confirm_cart(session=session, idempotency_key="no-address", fulfillment_type="delivery")
    other_org, other_branch, _, _ = phase9_context("other-advanced")
    Campaign.objects.create(organization=other_org, branch=other_branch, name="Foreign", code="FOREIGN", kind="fixed", value=1, starts_at=timezone.now() - timedelta(days=1), ends_at=timezone.now() + timedelta(days=1))
    with pytest.raises(Exception):
        confirm_cart(session=session, idempotency_key="foreign-code", promotion_code="FOREIGN")
    assert not Order.objects.filter(organization=org).exists()
