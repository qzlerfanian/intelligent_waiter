from datetime import timedelta
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.branches.models import Branch, BranchAssignment
from apps.customers.models import TableSession
from apps.identity.models import GuestIdentity
from apps.orders.models import NotificationOutbox, Order, OrderStatusEvent
from apps.organizations.models import Membership, Organization, Role
from apps.tables.models import RestaurantTable

User = get_user_model()

def setup_order(role=Role.CASHIER, status=Order.Status.PENDING):
    organization = Organization.objects.create(name="Operations", slug=f"ops-{role}-{status}")
    branch = Branch.objects.create(organization=organization, name="Main", code="main")
    table = RestaurantTable.objects.create(organization=organization, branch=branch, number="1", qr_token_hash=f"{role}-{status}".ljust(64, "x"))
    guest = GuestIdentity.objects.create(expires_at=timezone.now() + timedelta(hours=5))
    session = TableSession.objects.create(organization=organization, branch=branch, table=table, guest=guest, token_hash=f"session-{role}-{status}".ljust(64, "y"), expires_at=timezone.now() + timedelta(hours=4))
    order = Order.objects.create(organization=organization, branch=branch, table=table, session=session, guest=guest, status=status, subtotal=1000, total=1000, idempotency_key=f"key-{role}-{status}")
    user = User.objects.create_user(email=f"{role}-{status}@example.com", password="password1234")
    Membership.objects.create(organization=organization, user=user, role=role)
    if role not in (Role.OWNER, Role.ADMIN):
        BranchAssignment.objects.create(branch=branch, user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}", HTTP_X_ORGANIZATION_ID=str(organization.id))
    return client, user, organization, branch, order

@pytest.mark.django_db
def test_cashier_confirms_pending_order_and_writes_audit_and_outbox():
    client, user, _, _, order = setup_order()
    response = client.patch(f"/api/v1/staff/orders/{order.id}/", {"status": "confirmed", "version": 1})
    assert response.status_code == 200
    order.refresh_from_db()
    assert order.status == Order.Status.CONFIRMED
    assert order.version == 2
    assert OrderStatusEvent.objects.filter(order=order, actor=user, from_status="pending", to_status="confirmed").exists()
    assert NotificationOutbox.objects.filter(topic="order.status_changed", payload__order_id=str(order.id)).exists()

@pytest.mark.django_db
def test_kitchen_cannot_confirm_pending_order():
    client, _, _, _, order = setup_order(Role.CHEF)
    response = client.patch(f"/api/v1/staff/orders/{order.id}/", {"status": "confirmed", "version": 1})
    assert response.status_code == 403

@pytest.mark.django_db
def test_kitchen_queue_hides_pending_orders():
    client, _, _, _, _ = setup_order(Role.CHEF)
    response = client.get("/api/v1/staff/orders/")
    assert response.status_code == 200
    assert response.json()["data"] == []

@pytest.mark.django_db
def test_chef_moves_confirmed_order_to_preparing():
    client, _, _, _, order = setup_order(Role.CHEF, Order.Status.CONFIRMED)
    response = client.patch(f"/api/v1/staff/orders/{order.id}/", {"status": "preparing", "version": 1})
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "preparing"

@pytest.mark.django_db
def test_stale_order_version_is_rejected():
    client, _, _, _, order = setup_order()
    client.patch(f"/api/v1/staff/orders/{order.id}/", {"status": "confirmed", "version": 1})
    response = client.patch(f"/api/v1/staff/orders/{order.id}/", {"status": "cancelled", "version": 1})
    assert response.status_code == 400

@pytest.mark.django_db
def test_staff_cannot_see_unassigned_branch_orders():
    client, user, organization, _, _ = setup_order(Role.WAITER)
    other_branch = Branch.objects.create(organization=organization, name="Other", code="other")
    table = RestaurantTable.objects.create(organization=organization, branch=other_branch, number="9", qr_token_hash="other".ljust(64, "z"))
    guest = GuestIdentity.objects.create(expires_at=timezone.now() + timedelta(hours=5))
    session = TableSession.objects.create(organization=organization, branch=other_branch, table=table, guest=guest, token_hash="other-session".ljust(64, "z"), expires_at=timezone.now() + timedelta(hours=4))
    hidden = Order.objects.create(organization=organization, branch=other_branch, table=table, session=session, guest=guest, subtotal=1, total=1, idempotency_key="hidden")
    response = client.get("/api/v1/staff/orders/")
    ids = {entry["id"] for entry in response.json()["data"]}
    assert str(hidden.id) not in ids

@pytest.mark.django_db
def test_invalid_state_machine_jump_is_rejected_even_for_owner():
    client, _, _, _, order = setup_order(Role.OWNER)
    response = client.patch(f"/api/v1/staff/orders/{order.id}/", {"status": "ready", "version": 1})
    assert response.status_code == 400
