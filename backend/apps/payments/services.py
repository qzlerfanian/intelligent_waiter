import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.orders.models import NotificationOutbox, Order

from .models import Invoice, PaymentAttempt, PaymentEvent


def order_payment_summary(order):
    attempts = order.payments.order_by("-created_at")
    paid = attempts.filter(status=PaymentAttempt.Status.PAID).first()
    latest = paid or attempts.first()
    if latest is None:
        return {"status": "unpaid", "method": None, "payment_id": None, "paid_at": None}
    return {"status": latest.status, "method": latest.method, "payment_id": str(latest.id), "paid_at": latest.paid_at}


@transaction.atomic
def create_payment(*, order, method, idempotency_key, actor=None):
    existing = PaymentAttempt.objects.filter(organization=order.organization, idempotency_key=idempotency_key).first()
    if existing:
        if existing.order_id != order.id or existing.method != method:
            raise ValidationError({"idempotency_key": "This key has already been used for another payment."})
        return existing, False
    if order.status == Order.Status.CANCELLED:
        raise ValidationError({"order": "A cancelled order cannot be paid."})
    if order.payments.filter(status=PaymentAttempt.Status.PAID).exists():
        raise ValidationError({"order": "This order is already paid."})
    gateway_token = uuid.uuid4() if method == PaymentAttempt.Method.ONLINE else None
    payment = PaymentAttempt.objects.create(
        organization=order.organization, branch=order.branch, order=order, method=method,
        amount=order.total, currency=order.currency, idempotency_key=idempotency_key,
        provider="mock_gateway" if method == PaymentAttempt.Method.ONLINE else "manual",
        gateway_token=gateway_token, created_by=actor,
    )
    PaymentEvent.objects.create(organization=order.organization, branch=order.branch, payment=payment, from_status="", to_status=payment.status, actor=actor, source="payment_created")
    return payment, True


@transaction.atomic
def mark_payment_paid(*, payment, source, actor=None, provider_reference=""):
    payment = PaymentAttempt.objects.select_for_update().select_related("order").get(pk=payment.pk)
    order = Order.objects.select_for_update().get(pk=payment.order_id)
    payment.order = order
    if payment.status == PaymentAttempt.Status.PAID:
        return payment, False
    if PaymentAttempt.objects.filter(order=order, status=PaymentAttempt.Status.PAID).exclude(pk=payment.pk).exists():
        raise ValidationError({"order": "This order is already paid."})
    if payment.status != PaymentAttempt.Status.PENDING:
        raise ValidationError({"payment": f"A {payment.status} payment cannot be completed."})
    if payment.amount != order.total or payment.currency != order.currency:
        raise ValidationError({"payment": "Payment amount no longer matches the order."})
    payment.status = PaymentAttempt.Status.PAID
    payment.paid_at = timezone.now()
    payment.provider_reference = provider_reference or f"{source}-{str(payment.id)[:12]}"
    payment.save(update_fields=["status", "paid_at", "provider_reference", "updated_at"])
    PaymentEvent.objects.create(organization=payment.organization, branch=payment.branch, payment=payment, from_status=PaymentAttempt.Status.PENDING, to_status=PaymentAttempt.Status.PAID, actor=actor, source=source, metadata={"reference": payment.provider_reference})
    Invoice.objects.get_or_create(order=order, defaults={"organization": payment.organization, "branch": payment.branch, "payment": payment, "number": f"BAR-{payment.created_at:%Y%m%d}-{str(payment.order_id)[:8].upper()}", "currency": payment.currency, "subtotal": order.subtotal, "total": payment.amount})
    superseded = list(PaymentAttempt.objects.filter(order=order, status=PaymentAttempt.Status.PENDING).exclude(pk=payment.pk))
    PaymentAttempt.objects.filter(pk__in=[item.pk for item in superseded]).update(status=PaymentAttempt.Status.CANCELLED)
    PaymentEvent.objects.bulk_create([PaymentEvent(organization=item.organization, branch=item.branch, payment=item, from_status=PaymentAttempt.Status.PENDING, to_status=PaymentAttempt.Status.CANCELLED, actor=actor, source="superseded_by_paid_payment") for item in superseded])
    NotificationOutbox.objects.create(organization=payment.organization, branch=payment.branch, topic="payment.paid", payload={"payment_id": str(payment.id), "order_id": str(payment.order_id), "amount": payment.amount, "currency": payment.currency})
    from apps.customers.intelligence import credit_payment_loyalty
    credit_payment_loyalty(payment)
    return payment, True


def mock_gateway_confirm(*, session, payment_id, gateway_token):
    payment = PaymentAttempt.objects.filter(id=payment_id, order__session=session, method=PaymentAttempt.Method.ONLINE).first()
    if payment is None:
        raise NotFound("Payment was not found.")
    if not payment.gateway_token or str(payment.gateway_token) != str(gateway_token):
        raise ValidationError({"gateway_token": "Gateway verification failed."})
    return mark_payment_paid(payment=payment, source="mock_gateway_callback", provider_reference=f"MOCK-{str(payment.id)[:12].upper()}")
