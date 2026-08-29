from django.db import transaction
from django.db.models import F
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.orders.models import Order
from apps.orders.services import add_cart_line, get_active_cart, serialize_cart

from .models import CustomerProfile, LoyaltyAccount, LoyaltyEntry, PrivacyRequest, ReorderAction


def require_claimed_customer(session, user):
    if not user or not user.is_authenticated or session.customer_id != user.id:
        raise PermissionDenied("Sign in and claim this table session to access customer data.")
    return user


def loyalty_tier(points):
    if points >= 2000:
        return "gold"
    if points >= 500:
        return "silver"
    return "bronze"


@transaction.atomic
def credit_payment_loyalty(payment):
    customer = payment.order.customer
    if customer is None:
        return None
    account, _ = LoyaltyAccount.objects.select_for_update().get_or_create(organization=payment.organization, customer=customer)
    key = f"payment:{payment.id}"
    if LoyaltyEntry.objects.filter(account=account, idempotency_key=key).exists():
        return account
    points = max(1, payment.amount // (100000 if payment.currency == "IRR" else 100))
    LoyaltyEntry.objects.create(account=account, order=payment.order, points=points, reason="paid_order", idempotency_key=key)
    LoyaltyAccount.objects.filter(pk=account.pk).update(points_balance=F("points_balance") + points, lifetime_points=F("lifetime_points") + points)
    account.refresh_from_db()
    account.tier = loyalty_tier(account.lifetime_points)
    account.save(update_fields=["tier", "updated_at"])
    return account


@transaction.atomic
def reorder(*, session, customer, source_order_id, idempotency_key):
    source = Order.objects.prefetch_related("lines").filter(id=source_order_id, customer=customer, organization=session.organization).first()
    if source is None:
        raise NotFound("Order was not found.")
    action, created = ReorderAction.objects.get_or_create(organization=session.organization, customer=customer, idempotency_key=idempotency_key, defaults={"source_order": source})
    if not created:
        if action.source_order_id != source.id:
            raise ValidationError({"idempotency_key": "This key has already been used."})
        return serialize_cart(get_active_cart(session)), False
    for line in source.lines.all():
        if line.menu_item_id is None:
            raise ValidationError({"order": f"{line.item_name} is no longer on the menu."})
        add_cart_line(session=session, menu_item_id=line.menu_item_id, quantity=line.quantity, option_ids=[entry["id"] for entry in line.options], add_ons=[{"add_on_id": entry["id"], "quantity": entry["quantity"]} for entry in line.add_ons], note=line.note)
    return serialize_cart(get_active_cart(session)), True


@transaction.atomic
def erase_personalization(customer):
    CustomerProfile.objects.update_or_create(customer=customer, defaults={"diet": "none", "allergen_codes": [], "disliked_ingredients": [], "spice_preference": None, "ai_personalization_consent": False, "retention_consent": False, "marketing_consent": False})
    customer.favorites.all().delete()
    return PrivacyRequest.objects.create(customer=customer)
