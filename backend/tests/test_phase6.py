from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.ai.tools import TOOL_DEFINITIONS, add_item_to_cart, execute_tool, prepare_checkout
from apps.branches.models import Branch
from apps.customers.models import TableSession
from apps.identity.models import GuestIdentity
from apps.menus.models import Category, Menu, MenuItem, OptionGroup
from apps.organizations.models import Organization
from apps.orders.models import CartLine, Order, OrderConfirmation
from apps.orders.services import update_cart_line
from apps.tables.models import RestaurantTable


def ai_restaurant(slug="phase6-cafe"):
    organization = Organization.objects.create(name="AI Cafe", slug=slug)
    branch = Branch.objects.create(organization=organization, name="Main", code="main")
    table = RestaurantTable.objects.create(organization=organization, branch=branch, number="1", qr_token_hash=(slug + "qr").ljust(64, "q"))
    guest = GuestIdentity.objects.create(expires_at=timezone.now() + timedelta(hours=5))
    raw_session_token = f"{slug}-session-token"
    session = TableSession.objects.create(organization=organization, branch=branch, table=table, guest=guest, token_hash=TableSession.hash_token(raw_session_token), expires_at=timezone.now() + timedelta(hours=4))
    menu = Menu.objects.create(organization=organization, branch=branch, name="Main", currency="IRR")
    category = Category.objects.create(organization=organization, menu=menu, name="Pizza")
    item = MenuItem.objects.create(organization=organization, category=category, name="Margherita", base_price=350000)
    return organization, branch, session, item, raw_session_token


@pytest.mark.django_db
def test_ai_cart_tool_uses_server_price_and_never_exposes_order_tool():
    _, _, session, item, _ = ai_restaurant()
    result = add_item_to_cart(session, str(item.id), 2, [], [], "")
    assert result["action"] == "cart_changed"
    assert result["cart"]["subtotal"] == item.base_price * 2
    assert {tool["name"] for tool in TOOL_DEFINITIONS}.isdisjoint({"confirm_order", "create_order"})


@pytest.mark.django_db
def test_required_options_block_ai_cart_mutation():
    organization, _, session, item, _ = ai_restaurant()
    OptionGroup.objects.create(organization=organization, menu_item=item, name="Size", min_selections=1, max_selections=1, is_required=True)
    result = execute_tool("add_item_to_cart", {"menu_item_id": str(item.id), "quantity": 1, "option_ids": [], "add_ons": [], "note": ""}, session)
    assert "error" in result
    assert not CartLine.objects.filter(cart__session=session).exists()


@pytest.mark.django_db
def test_ai_cannot_add_another_tenants_item():
    _, _, session, _, _ = ai_restaurant()
    _, _, _, foreign_item, _ = ai_restaurant("foreign-ai-cafe")
    result = execute_tool("add_item_to_cart", {"menu_item_id": str(foreign_item.id), "quantity": 1, "option_ids": [], "add_ons": [], "note": ""}, session)
    assert "error" in result
    assert not CartLine.objects.filter(cart__session=session).exists()


@pytest.mark.django_db
def test_checkout_preview_does_not_create_order_and_cart_change_invalidates_it():
    _, _, session, item, _ = ai_restaurant()
    added = add_item_to_cart(session, str(item.id), 1, [], [], "")
    preview = prepare_checkout(session)
    assert Order.objects.count() == 0
    update_cart_line(session=session, line_id=added["cart"]["lines"][0]["id"], quantity=2)
    assert OrderConfirmation.objects.get(id=preview["confirmation_id"]).status == OrderConfirmation.Status.CANCELLED


@pytest.mark.django_db
def test_explicit_confirmation_endpoint_is_session_scoped_and_single_use():
    _, _, session, item, token = ai_restaurant()
    add_item_to_cart(session, str(item.id), 1, [], [], "")
    preview = prepare_checkout(session)
    client = APIClient(); client.credentials(HTTP_X_TABLE_SESSION=token)
    response = client.post(f'/api/v1/customer/chat/confirmations/{preview["confirmation_id"]}/confirm/')
    assert response.status_code == 201
    assert Order.objects.filter(session=session).count() == 1
    assert client.post(f'/api/v1/customer/chat/confirmations/{preview["confirmation_id"]}/confirm/').status_code == 404
    assert Order.objects.filter(session=session).count() == 1


@pytest.mark.django_db
@override_settings(AI_PROVIDER="local", OPENAI_API_KEY="")
def test_only_exact_affirmative_chat_message_confirms_pending_checkout():
    _, _, session, item, token = ai_restaurant()
    add_item_to_cart(session, str(item.id), 1, [], [], "")
    prepare_checkout(session)
    client = APIClient(); client.credentials(HTTP_X_TABLE_SESSION=token)
    vague = client.post("/api/v1/customer/chat/messages/", {"content": "شاید آره"})
    assert vague.status_code == 201
    assert Order.objects.count() == 0
    confirmed = client.post("/api/v1/customer/chat/messages/", {"content": "تأیید می‌کنم"})
    assert confirmed.status_code == 201
    action = confirmed.json()["data"]["message"]["actions"][0]
    assert action["type"] == "order_confirmed"
    assert Order.objects.filter(session=session).count() == 1
