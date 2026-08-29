import pytest
from django.test import override_settings
from rest_framework.test import APIClient
from apps.branches.models import Branch
from apps.orders.models import NotificationOutbox
from apps.orders.tasks import dispatch_outbox
from apps.organizations.models import Organization

@pytest.mark.django_db
def test_liveness_and_readiness_are_distinct_and_return_request_id():
    client = APIClient()
    live = client.get("/api/v1/health/", HTTP_X_REQUEST_ID="phase10-request")
    ready = client.get("/api/v1/ready/")
    assert live.status_code == 200 and live["X-Request-ID"] == "phase10-request"
    assert ready.status_code == 200 and ready.json()["data"]["checks"] == {"database": "ok", "redis": "ok"}

@pytest.mark.django_db
@override_settings(METRICS_TOKEN="secret-metrics")
def test_metrics_are_hidden_without_token_and_prometheus_compatible_with_token():
    client = APIClient()
    assert client.get("/api/v1/metrics/").status_code == 404
    response = client.get("/api/v1/metrics/", HTTP_AUTHORIZATION="Bearer secret-metrics")
    assert response.status_code == 200
    assert b"baran_http_requests_total" in response.content and b"baran_outbox_pending" in response.content

@pytest.mark.django_db
def test_outbox_dispatch_is_idempotent():
    organization = Organization.objects.create(name="Scale", slug="scale")
    branch = Branch.objects.create(organization=organization, name="Main", code="main")
    event = NotificationOutbox.objects.create(organization=organization, branch=branch, topic="test.event", payload={"ok": True})
    assert dispatch_outbox.run() >= 1
    event.refresh_from_db()
    assert event.status == NotificationOutbox.Status.PROCESSED and event.attempts == 1
    dispatch_outbox.run()
    event.refresh_from_db()
    assert event.attempts == 1
