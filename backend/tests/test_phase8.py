from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.ai.tools import get_customer_context
from apps.branches.models import Branch
from apps.customers.models import CustomerProfile, Favorite, LoyaltyAccount, PrivacyRequest, TableSession
from apps.identity.models import GuestIdentity
from apps.menus.models import Category, Menu, MenuItem
from apps.orders.models import Order, OrderLine
from apps.organizations.models import Organization
from apps.payments.models import PaymentAttempt
from apps.payments.services import create_payment, mark_payment_paid
from apps.tables.models import RestaurantTable

User = get_user_model()


def intelligence_context(slug="smart-cafe", claimed=True):
    organization = Organization.objects.create(name="Smart Cafe", slug=slug)
    branch = Branch.objects.create(organization=organization, name="Main", code="main")
    table = RestaurantTable.objects.create(organization=organization, branch=branch, number="1", qr_token_hash=(slug + "qr").ljust(64, "x"))
    guest = GuestIdentity.objects.create(expires_at=timezone.now() + timedelta(hours=4))
    user = User.objects.create_user(email=f"{slug}@example.com", password="password1234")
    raw_token = f"{slug}-session"
    session = TableSession.objects.create(organization=organization, branch=branch, table=table, guest=guest, customer=user if claimed else None, token_hash=TableSession.hash_token(raw_token), expires_at=timezone.now() + timedelta(hours=3))
    menu = Menu.objects.create(organization=organization, branch=branch, name="Main", currency="IRR")
    category = Category.objects.create(organization=organization, menu=menu, name="Food")
    item = MenuItem.objects.create(organization=organization, category=category, name="Soup", base_price=250000)
    client = APIClient(); client.credentials(HTTP_X_TABLE_SESSION=raw_token, HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client, organization, session, user, item


@pytest.mark.django_db
def test_personal_data_requires_authenticated_owner_of_claimed_session():
    _, _, session, _, _ = intelligence_context()
    anonymous = APIClient(); anonymous.credentials(HTTP_X_TABLE_SESSION="not-the-token")
    assert anonymous.get("/api/v1/customer/account/profile/").status_code == 401
    other = User.objects.create_user(email="other@example.com", password="password1234")
    wrong = APIClient(); wrong.credentials(HTTP_X_TABLE_SESSION=f"smart-cafe-session", HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(other).access_token}")
    assert wrong.get("/api/v1/customer/account/profile/").status_code == 403
    assert session.customer_id is not None


@pytest.mark.django_db
def test_ai_personalization_is_consent_gated():
    client, _, session, _, _ = intelligence_context()
    assert get_customer_context(session)["available"] is False
    response = client.patch("/api/v1/customer/account/profile/", {"diet": "vegan", "allergen_codes": ["NUTS"], "ai_personalization_consent": True}, format="json")
    assert response.status_code == 200
    context = get_customer_context(session)
    assert context["available"] is True
    assert context["diet"] == "vegan" and context["allergen_codes"] == ["nuts"]


@pytest.mark.django_db
def test_favorites_are_tenant_scoped():
    client, organization, _, user, item = intelligence_context()
    assert client.post("/api/v1/customer/account/favorites/", {"menu_item_id": item.id}).status_code == 201
    _, _, _, _, foreign_item = intelligence_context("foreign-smart-cafe")
    assert client.post("/api/v1/customer/account/favorites/", {"menu_item_id": foreign_item.id}).status_code == 404
    assert Favorite.objects.filter(organization=organization, customer=user).count() == 1


@pytest.mark.django_db
def test_reorder_uses_current_server_price_and_is_idempotent():
    client, organization, session, user, item = intelligence_context()
    order = Order.objects.create(organization=organization, branch=session.branch, table=session.table, session=session, customer=user, subtotal=100000, total=100000, idempotency_key="old-order")
    OrderLine.objects.create(order=order, menu_item=item, item_name=item.name, quantity=2, unit_price=100000, options=[], add_ons=[], line_total=200000)
    first = client.post(f"/api/v1/customer/account/orders/{order.id}/reorder/", HTTP_IDEMPOTENCY_KEY="reorder-once")
    second = client.post(f"/api/v1/customer/account/orders/{order.id}/reorder/", HTTP_IDEMPOTENCY_KEY="reorder-once")
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["data"]["subtotal"] == 500000
    assert first.json()["data"]["lines"][0]["unit_price"] == 250000
    assert len(second.json()["data"]["lines"]) == 1


@pytest.mark.django_db
def test_paid_order_credits_loyalty_exactly_once():
    _, organization, session, user, _ = intelligence_context()
    order = Order.objects.create(organization=organization, branch=session.branch, table=session.table, session=session, customer=user, subtotal=450000, total=450000, idempotency_key="loyal-order")
    payment, _ = create_payment(order=order, method=PaymentAttempt.Method.CASH, idempotency_key="loyal-payment")
    mark_payment_paid(payment=payment, source="test")
    mark_payment_paid(payment=payment, source="test")
    account = LoyaltyAccount.objects.get(organization=organization, customer=user)
    assert account.points_balance == 4
    assert account.entries.count() == 1


@pytest.mark.django_db
def test_privacy_erasure_clears_preferences_favorites_and_consent():
    client, _, _, user, item = intelligence_context()
    client.patch("/api/v1/customer/account/profile/", {"diet": "vegetarian", "allergen_codes": ["dairy"], "ai_personalization_consent": True}, format="json")
    client.post("/api/v1/customer/account/favorites/", {"menu_item_id": item.id})
    response = client.post("/api/v1/customer/account/privacy/erase/", {"confirmation": "DELETE MY PERSONALIZATION"})
    assert response.status_code == 201
    profile = CustomerProfile.objects.get(customer=user)
    assert profile.diet == "none" and profile.allergen_codes == [] and not profile.ai_personalization_consent
    assert not Favorite.objects.filter(customer=user).exists()
    assert PrivacyRequest.objects.filter(customer=user, status="completed").exists()
