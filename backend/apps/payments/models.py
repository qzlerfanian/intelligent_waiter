import uuid

from django.db import models

from apps.branches.models import Branch
from apps.identity.models import User
from apps.orders.models import Order
from apps.organizations.models import Organization


class PaymentAttempt(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        POS = "pos", "Card terminal"
        ONLINE = "online", "Online"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="payments")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="payments")
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments")
    method = models.CharField(max_length=16, choices=Method.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    amount = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    idempotency_key = models.CharField(max_length=128)
    provider = models.CharField(max_length=40, default="manual")
    provider_reference = models.CharField(max_length=120, blank=True)
    gateway_token = models.UUIDField(null=True, blank=True, unique=True)
    failure_code = models.CharField(max_length=80, blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_payments")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "idempotency_key"], name="unique_payment_idempotency_org"),
            models.UniqueConstraint(fields=["order"], condition=models.Q(status="paid"), name="one_paid_payment_per_order"),
        ]
        indexes = [models.Index(fields=["organization", "branch", "status", "created_at"], name="payment_scope_status_idx")]


class PaymentEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="payment_events")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="payment_events")
    payment = models.ForeignKey(PaymentAttempt, on_delete=models.CASCADE, related_name="events")
    from_status = models.CharField(max_length=16, blank=True)
    to_status = models.CharField(max_length=16, choices=PaymentAttempt.Status.choices)
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="payment_events")
    source = models.CharField(max_length=32)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class Invoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="invoices")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="invoices")
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="invoice")
    payment = models.OneToOneField(PaymentAttempt, on_delete=models.PROTECT, related_name="invoice")
    number = models.CharField(max_length=40)
    currency = models.CharField(max_length=3)
    subtotal = models.PositiveBigIntegerField()
    total = models.PositiveBigIntegerField()
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "number"], name="unique_invoice_number_org")]
