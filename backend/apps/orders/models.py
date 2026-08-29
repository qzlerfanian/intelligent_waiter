import uuid
from django.db import models
from apps.branches.models import Branch
from apps.customers.models import TableSession
from apps.identity.models import GuestIdentity, User
from apps.menus.models import AddOn, MenuItem, Option
from apps.organizations.models import Organization
from apps.tables.models import RestaurantTable

class Cart(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CONVERTED = "converted", "Converted"
        ABANDONED = "abandoned", "Abandoned"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="carts")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="carts")
    session = models.ForeignKey(TableSession, on_delete=models.CASCADE, related_name="carts")
    currency = models.CharField(max_length=3, default="IRR")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["session"], condition=models.Q(status="active"), name="one_active_cart_per_session")]
        indexes = [models.Index(fields=["organization", "branch", "status"], name="orders_cart_scope_idx")]

class CartLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="lines")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT, related_name="cart_lines")
    quantity = models.PositiveSmallIntegerField(default=1)
    unit_price = models.PositiveBigIntegerField()
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gte=1), name="cart_line_quantity_at_least_one")]

class CartLineOption(models.Model):
    line = models.ForeignKey(CartLine, on_delete=models.CASCADE, related_name="selected_options")
    option = models.ForeignKey(Option, on_delete=models.PROTECT)
    price_delta = models.BigIntegerField(default=0)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["line", "option"], name="unique_cart_line_option")]

class CartLineAddOn(models.Model):
    line = models.ForeignKey(CartLine, on_delete=models.CASCADE, related_name="selected_add_ons")
    add_on = models.ForeignKey(AddOn, on_delete=models.PROTECT)
    quantity = models.PositiveSmallIntegerField(default=1)
    unit_price = models.PositiveBigIntegerField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=["line", "add_on"], name="unique_cart_line_addon"), models.CheckConstraint(condition=models.Q(quantity__gte=1), name="cart_addon_quantity_at_least_one")]

class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PREPARING = "preparing", "Preparing"
        READY = "ready", "Ready"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Fulfillment(models.TextChoices):
        DINE_IN = "dine_in", "Dine in"
        TAKEAWAY = "takeaway", "Takeaway"
        DELIVERY = "delivery", "Delivery"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="orders")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="orders")
    table = models.ForeignKey(RestaurantTable, on_delete=models.PROTECT, related_name="orders")
    session = models.ForeignKey(TableSession, on_delete=models.PROTECT, related_name="orders")
    guest = models.ForeignKey(GuestIdentity, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    customer = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="customer_orders")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    currency = models.CharField(max_length=3, default="IRR")
    subtotal = models.PositiveBigIntegerField()
    total = models.PositiveBigIntegerField()
    discount_total = models.PositiveBigIntegerField(default=0)
    promotion_code = models.CharField(max_length=40, blank=True)
    fulfillment_type = models.CharField(max_length=16, choices=Fulfillment.choices, default=Fulfillment.DINE_IN)
    delivery_address = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=128)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "idempotency_key"], name="unique_order_idempotency_per_org")]
        indexes = [models.Index(fields=["organization", "branch", "status", "created_at"], name="orders_order_scope_idx")]

class OrderLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    menu_item = models.ForeignKey(MenuItem, null=True, on_delete=models.SET_NULL, related_name="order_lines")
    item_name = models.CharField(max_length=160)
    quantity = models.PositiveSmallIntegerField()
    unit_price = models.PositiveBigIntegerField()
    options = models.JSONField(default=list)
    add_ons = models.JSONField(default=list)
    note = models.CharField(max_length=500, blank=True)
    line_total = models.PositiveBigIntegerField()

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gte=1), name="order_line_quantity_at_least_one")]

class OrderStatusEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="order_events")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="order_events")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_events")
    from_status = models.CharField(max_length=16, blank=True)
    to_status = models.CharField(max_length=16, choices=Order.Status.choices)
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="order_status_events")
    reason = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["organization", "branch", "created_at"], name="orders_event_scope_idx")]

class NotificationOutbox(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="notification_outbox")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="notification_outbox")
    topic = models.CharField(max_length=80)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["status", "available_at"], name="orders_outbox_pending_idx"), models.Index(fields=["organization", "branch", "created_at"], name="orders_outbox_scope_idx")]

class OrderConfirmation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="order_confirmations")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="order_confirmations")
    session = models.ForeignKey(TableSession, on_delete=models.CASCADE, related_name="order_confirmations")
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="confirmations")
    cart_fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    expires_at = models.DateTimeField()
    order = models.OneToOneField(Order, null=True, blank=True, on_delete=models.SET_NULL, related_name="confirmation")
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["session", "status", "expires_at"], name="order_confirmation_lookup_idx")]
