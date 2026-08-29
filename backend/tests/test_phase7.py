from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.branches.models import Branch, BranchAssignment
from apps.customers.models import TableSession
from apps.identity.models import GuestIdentity
from apps.orders.models import NotificationOutbox, Order
from apps.organizations.models import Membership, Organization, Role
from apps.payments.models import Invoice, PaymentAttempt, PaymentEvent
from apps.tables.models import RestaurantTable

User = get_user_model()


def payment_context(slug="pay-cafe", role=Role.CASHIER):
    organization = Organization.objects.create(name="Pay Cafe", slug=slug)
    branch = Branch.objects.create(organization=organization, name="Main", code="main")
    table = RestaurantTable.objects.create(organization=organization, branch=branch, number="1", qr_token_hash=(slug + "qr").ljust(64, "x"))
    guest = GuestIdentity.objects.create(expires_at=timezone.now() + timedelta(hours=3))
    raw_token = f"{slug}-table-token"
    session = TableSession.objects.create(organization=organization, branch=branch, table=table, guest=guest, token_hash=TableSession.hash_token(raw_token), expires_at=timezone.now() + timedelta(hours=2))
    order = Order.objects.create(organization=organization, branch=branch, table=table, session=session, guest=guest, subtotal=420000, total=420000, idempotency_key=f"order-{slug}")
    customer = APIClient(); customer.credentials(HTTP_X_TABLE_SESSION=raw_token)
    user = User.objects.create_user(email=f"{slug}@example.com", password="password1234")
    Membership.objects.create(organization=organization, user=user, role=role)
    if role not in (Role.OWNER, Role.ADMIN):
        BranchAssignment.objects.create(branch=branch, user=user)
    staff = APIClient(); staff.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}", HTTP_X_ORGANIZATION_ID=str(organization.id))
    return customer, staff, session, order


@pytest.mark.django_db
def test_online_payment_uses_order_total_and_issues_invoice_after_verified_callback():
    customer, _, _, order = payment_context()
    response = customer.post("/api/v1/customer/payments/", {"order_id": order.id, "method": "online", "amount": 1}, HTTP_IDEMPOTENCY_KEY="online-1")
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["amount"] == 420000
    confirmed = customer.post(f'/api/v1/customer/payments/{data["id"]}/mock-confirm/', {"token": data["checkout"]["token"]})
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["status"] == "paid"
    assert Invoice.objects.filter(order=order, total=420000).exists()
    assert NotificationOutbox.objects.filter(topic="payment.paid", payload__order_id=str(order.id)).exists()


@pytest.mark.django_db
def test_payment_creation_is_idempotent():
    customer, _, _, order = payment_context()
    first = customer.post("/api/v1/customer/payments/", {"order_id": order.id, "method": "online"}, HTTP_IDEMPOTENCY_KEY="same-key")
    second = customer.post("/api/v1/customer/payments/", {"order_id": order.id, "method": "online"}, HTTP_IDEMPOTENCY_KEY="same-key")
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert PaymentAttempt.objects.count() == 1


@pytest.mark.django_db
def test_wrong_session_and_wrong_gateway_token_cannot_confirm_payment():
    customer, _, _, order = payment_context()
    data = customer.post("/api/v1/customer/payments/", {"order_id": order.id, "method": "online"}, HTTP_IDEMPOTENCY_KEY="secure-key").json()["data"]
    other_customer, _, _, _ = payment_context("other-pay-cafe")
    assert other_customer.post(f'/api/v1/customer/payments/{data["id"]}/mock-confirm/', {"token": data["checkout"]["token"]}).status_code == 404
    assert customer.post(f'/api/v1/customer/payments/{data["id"]}/mock-confirm/', {"token": "00000000-0000-0000-0000-000000000000"}).status_code == 400
    assert not Invoice.objects.filter(order=order).exists()


@pytest.mark.django_db
def test_cashier_can_collect_cash_with_audit_event():
    _, staff, _, order = payment_context()
    response = staff.post(f"/api/v1/staff/orders/{order.id}/collect-payment/", {"method": "cash"}, HTTP_IDEMPOTENCY_KEY="cash-1")
    assert response.status_code == 200
    payment = PaymentAttempt.objects.get(order=order)
    assert payment.status == PaymentAttempt.Status.PAID
    assert payment.created_by is not None
    assert PaymentEvent.objects.filter(payment=payment, source="staff_collection", to_status="paid").exists()


@pytest.mark.django_db
def test_kitchen_staff_cannot_collect_payment():
    _, staff, _, order = payment_context(role=Role.CHEF)
    response = staff.post(f"/api/v1/staff/orders/{order.id}/collect-payment/", {"method": "cash"}, HTTP_IDEMPOTENCY_KEY="forbidden")
    assert response.status_code == 403
    assert not PaymentAttempt.objects.exists()
