import secrets
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, NotFound, PermissionDenied
from apps.identity.models import GuestIdentity
from apps.tables.models import RestaurantTable, TableStatus
from .models import TableSession

@transaction.atomic
def start_table_session(qr_token):
    table = RestaurantTable.objects.select_related("organization", "branch").filter(qr_token_hash=RestaurantTable.hash_token(qr_token), is_active=True, branch__is_active=True, organization__is_active=True).first()
    if table is None:
        raise NotFound("QR code is invalid or inactive.")
    if table.status == TableStatus.OUT_OF_SERVICE:
        raise PermissionDenied("This table is currently out of service.")
    now = timezone.now()
    guest = GuestIdentity.objects.create(expires_at=now + timedelta(hours=12))
    raw_token = secrets.token_urlsafe(32)
    session = TableSession.objects.create(organization=table.organization, branch=table.branch, table=table, guest=guest, token_hash=TableSession.hash_token(raw_token), expires_at=now + timedelta(hours=4))
    return session, raw_token

def resolve_table_session(request, *, lock=False):
    raw_token = request.headers.get("X-Table-Session")
    if not raw_token:
        raise AuthenticationFailed("X-Table-Session is required.", code="table_session_required")
    queryset = TableSession.objects.select_related("organization", "branch", "table", "guest", "customer")
    if lock:
        queryset = queryset.select_for_update()
    session = queryset.filter(token_hash=TableSession.hash_token(raw_token), status=TableSession.Status.ACTIVE).first()
    if session is None:
        raise AuthenticationFailed("Table session is invalid.", code="invalid_table_session")
    if session.expires_at <= timezone.now():
        TableSession.objects.filter(pk=session.pk).update(status=TableSession.Status.EXPIRED)
        raise AuthenticationFailed("Table session has expired.", code="expired_table_session")
    return session
