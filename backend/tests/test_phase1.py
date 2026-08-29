import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.branches.models import Branch
from apps.organizations.models import Membership, Organization, Role

User = get_user_model()

def client_for(user, organization=None):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    if organization:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}", HTTP_X_ORGANIZATION_ID=str(organization.id))
    return client

@pytest.mark.django_db
def test_registration_hashes_password(client):
    response = client.post("/api/v1/auth/register/", {"email": "owner@example.com", "display_name": "Owner", "password": "a-strong-password"})
    assert response.status_code == 201
    assert User.objects.get(email="owner@example.com").check_password("a-strong-password")

@pytest.mark.django_db
def test_organization_creator_becomes_owner():
    user = User.objects.create_user(email="owner@example.com", password="password1234")
    response = client_for(user).post("/api/v1/organizations/", {"name": "Cafe X", "slug": "cafe-x"})
    assert response.status_code == 201
    assert Membership.objects.get(user=user).role == Role.OWNER

@pytest.mark.django_db
def test_tenant_header_cannot_cross_organizations():
    user = User.objects.create_user(email="member@example.com", password="password1234")
    allowed = Organization.objects.create(name="Allowed", slug="allowed")
    denied = Organization.objects.create(name="Denied", slug="denied")
    Membership.objects.create(user=user, organization=allowed, role=Role.ADMIN)
    response = client_for(user, denied).get("/api/v1/organizations/branches/")
    assert response.status_code == 403

@pytest.mark.django_db
def test_branch_queries_are_tenant_scoped():
    user = User.objects.create_user(email="admin@example.com", password="password1234")
    first = Organization.objects.create(name="First", slug="first")
    second = Organization.objects.create(name="Second", slug="second")
    Membership.objects.create(user=user, organization=first, role=Role.ADMIN)
    Branch.objects.create(organization=first, name="Visible", code="visible")
    Branch.objects.create(organization=second, name="Hidden", code="hidden")
    response = client_for(user, first).get("/api/v1/organizations/branches/")
    assert response.status_code == 200
    assert [branch["name"] for branch in response.json()] == ["Visible"]

@pytest.mark.django_db
def test_non_admin_cannot_manage_branches():
    user = User.objects.create_user(email="waiter@example.com", password="password1234")
    organization = Organization.objects.create(name="Cafe", slug="cafe")
    Membership.objects.create(user=user, organization=organization, role=Role.WAITER)
    response = client_for(user, organization).post("/api/v1/organizations/branches/", {"name": "New", "code": "new"})
    assert response.status_code == 403
