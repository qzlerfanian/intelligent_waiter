import secrets
from django.db import transaction
from django.utils import timezone
from .models import RestaurantTable

def issue_qr_token():
    token = secrets.token_urlsafe(32)
    return token, RestaurantTable.hash_token(token)

@transaction.atomic
def rotate_qr_token(table):
    token, token_hash = issue_qr_token()
    table.qr_token_hash = token_hash
    table.qr_rotated_at = timezone.now()
    table.save(update_fields=["qr_token_hash", "qr_rotated_at", "updated_at"])
    return token
