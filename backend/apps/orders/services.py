import hashlib
import json
from datetime import timedelta
from django.db import models, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from apps.menus.models import BranchItemAvailability, MenuItem, Option, AddOn
from .models import Cart, CartLine, CartLineAddOn, CartLineOption, NotificationOutbox, Order, OrderConfirmation, OrderLine, OrderStatusEvent

def get_active_cart(session):
    cart, _ = Cart.objects.get_or_create(session=session, status=Cart.Status.ACTIVE, defaults={"organization": session.organization, "branch": session.branch})
    return cart

def effective_item(item, branch, requested_quantity=1):
    menu_branch_id = item.category.menu.branch_id
    if item.organization_id != branch.organization_id or (menu_branch_id is not None and menu_branch_id != branch.id):
        raise NotFound("Menu item was not found for this branch.")
    override = BranchItemAvailability.objects.filter(branch=branch, menu_item=item).first()
    available = item.is_active and item.is_available and item.category.is_active and item.category.menu.is_active
    if override:
        available = available and override.is_available and (override.stock_quantity is None or override.stock_quantity > 0)
        if override.stock_quantity is not None and requested_quantity > override.stock_quantity:
            available = False
    if not available:
        raise ValidationError({"menu_item": "This item is currently unavailable."})
    price = override.price_override if override and override.price_override is not None else (item.discount_price if item.discount_price is not None else item.base_price)
    return price

def validate_customizations(item, option_ids, add_on_inputs):
    options = list(Option.objects.filter(id__in=option_ids, group__menu_item=item, is_available=True).select_related("group"))
    if len(options) != len(set(option_ids)):
        raise ValidationError({"option_ids": "One or more selected options are invalid."})
    counts = {}
    for option in options:
        counts[option.group_id] = counts.get(option.group_id, 0) + 1
    for group in item.option_groups.all():
        count = counts.get(group.id, 0)
        minimum = max(group.min_selections, 1 if group.is_required else 0)
        if count < minimum or count > group.max_selections:
            raise ValidationError({"option_ids": f"Select between {minimum} and {group.max_selections} options for {group.name}."})
    requested = {str(entry["add_on_id"]): entry["quantity"] for entry in add_on_inputs}
    add_ons = list(AddOn.objects.filter(id__in=requested, menu_item=item, is_available=True))
    if len(add_ons) != len(requested):
        raise ValidationError({"add_ons": "One or more add-ons are invalid."})
    for add_on in add_ons:
        if requested[str(add_on.id)] < 1 or requested[str(add_on.id)] > add_on.max_quantity:
            raise ValidationError({"add_ons": f"Invalid quantity for {add_on.name}."})
    return options, [(add_on, requested[str(add_on.id)]) for add_on in add_ons]

@transaction.atomic
def add_cart_line(*, session, menu_item_id, quantity, option_ids, add_ons, note=""):
    item = MenuItem.objects.select_related("organization", "category__menu").prefetch_related("option_groups").filter(id=menu_item_id).first()
    if item is None:
        raise NotFound("Menu item was not found.")
    unit_price = effective_item(item, session.branch, quantity)
    options, selected_add_ons = validate_customizations(item, option_ids, add_ons)
    cart = get_active_cart(session)
    item_currency = item.category.menu.currency
    if not cart.lines.exists() and cart.currency != item_currency:
        cart.currency = item_currency
        cart.save(update_fields=["currency", "updated_at"])
    elif cart.currency != item_currency:
        raise ValidationError({"menu_item": "Items with different currencies cannot share a cart."})
    line = CartLine.objects.create(cart=cart, menu_item=item, quantity=quantity, unit_price=unit_price, note=note)
    CartLineOption.objects.bulk_create([CartLineOption(line=line, option=option, price_delta=option.price_delta) for option in options])
    CartLineAddOn.objects.bulk_create([CartLineAddOn(line=line, add_on=add_on, quantity=count, unit_price=add_on.price) for add_on, count in selected_add_ons])
    OrderConfirmation.objects.filter(session=session, status=OrderConfirmation.Status.PENDING).update(status=OrderConfirmation.Status.CANCELLED)
    return line

def line_total(line):
    option_total = sum(entry.price_delta for entry in line.selected_options.all())
    add_on_total = sum(entry.unit_price * entry.quantity for entry in line.selected_add_ons.all())
    return (line.unit_price + option_total + add_on_total) * line.quantity

def serialize_cart(cart):
    lines = cart.lines.select_related("menu_item").prefetch_related("selected_options__option", "selected_add_ons__add_on")
    result = []
    for line in lines:
        result.append({"id": str(line.id), "menu_item_id": str(line.menu_item_id), "name": line.menu_item.name, "quantity": line.quantity, "unit_price": line.unit_price, "options": [{"id": str(value.option_id), "name": value.option.name, "price_delta": value.price_delta} for value in line.selected_options.all()], "add_ons": [{"id": str(value.add_on_id), "name": value.add_on.name, "quantity": value.quantity, "unit_price": value.unit_price} for value in line.selected_add_ons.all()], "note": line.note, "line_total": line_total(line)})
    return {"id": str(cart.id), "currency": cart.currency, "lines": result, "subtotal": sum(value["line_total"] for value in result)}

def cart_fingerprint(cart):
    payload = serialize_cart(cart)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

@transaction.atomic
def update_cart_line(*, session, line_id, quantity=None, note=None):
    line = CartLine.objects.select_for_update().select_related("cart", "menu_item__category__menu").filter(id=line_id, cart__session=session, cart__status=Cart.Status.ACTIVE).first()
    if line is None:
        raise NotFound("Cart line was not found.")
    if quantity is not None:
        other_quantity = CartLine.objects.filter(cart=line.cart, menu_item=line.menu_item).exclude(pk=line.pk).aggregate(total=models.Sum("quantity"))["total"] or 0
        effective_item(line.menu_item, session.branch, other_quantity + quantity)
        line.quantity = quantity
    if note is not None:
        line.note = note
    line.save(update_fields=[field for field, value in (("quantity", quantity), ("note", note)) if value is not None] + ["updated_at"])
    OrderConfirmation.objects.filter(session=session, status=OrderConfirmation.Status.PENDING).update(status=OrderConfirmation.Status.CANCELLED)
    return line

@transaction.atomic
def remove_cart_line(*, session, line_id):
    deleted, _ = CartLine.objects.filter(id=line_id, cart__session=session, cart__status=Cart.Status.ACTIVE).delete()
    if not deleted:
        raise NotFound("Cart line was not found.")
    OrderConfirmation.objects.filter(session=session, status=OrderConfirmation.Status.PENDING).update(status=OrderConfirmation.Status.CANCELLED)

@transaction.atomic
def prepare_order_confirmation(*, session):
    cart = Cart.objects.select_for_update().filter(session=session, status=Cart.Status.ACTIVE).first()
    if cart is None or not cart.lines.exists():
        raise ValidationError({"cart": "The cart is empty."})
    OrderConfirmation.objects.filter(session=session, status=OrderConfirmation.Status.PENDING).update(status=OrderConfirmation.Status.CANCELLED)
    confirmation = OrderConfirmation.objects.create(organization=session.organization, branch=session.branch, session=session, cart=cart, cart_fingerprint=cart_fingerprint(cart), expires_at=timezone.now() + timedelta(minutes=10))
    return confirmation, serialize_cart(cart)

@transaction.atomic
def confirm_order_confirmation(*, session, confirmation_id):
    confirmation = OrderConfirmation.objects.select_for_update().filter(id=confirmation_id, session=session, status=OrderConfirmation.Status.PENDING).first()
    if confirmation is None:
        raise NotFound("Order confirmation was not found or is no longer active.")
    if confirmation.expires_at <= timezone.now():
        confirmation.status = OrderConfirmation.Status.EXPIRED
        confirmation.save(update_fields=["status"])
        raise ValidationError({"confirmation": "Order confirmation has expired."})
    if confirmation.cart.status != Cart.Status.ACTIVE or cart_fingerprint(confirmation.cart) != confirmation.cart_fingerprint:
        confirmation.status = OrderConfirmation.Status.CANCELLED
        confirmation.save(update_fields=["status"])
        raise ValidationError({"confirmation": "The cart changed. Review it and confirm again."})
    order, _ = confirm_cart(session=session, idempotency_key=f"ai-confirm:{confirmation.id}")
    confirmation.status = OrderConfirmation.Status.CONFIRMED
    confirmation.order = order
    confirmation.confirmed_at = timezone.now()
    confirmation.save(update_fields=["status", "order", "confirmed_at"])
    return order

@transaction.atomic
def confirm_cart(*, session, idempotency_key, promotion_code="", fulfillment_type="dine_in", delivery_address=""):
    existing = Order.objects.filter(organization=session.organization, idempotency_key=idempotency_key).first()
    if existing:
        if existing.session_id != session.id:
            raise ValidationError({"idempotency_key": "This key has already been used."})
        return existing, False
    cart = Cart.objects.select_for_update().filter(session=session, status=Cart.Status.ACTIVE).first()
    if cart is None or not cart.lines.exists():
        raise ValidationError({"cart": "The cart is empty."})
    lines = list(cart.lines.select_related("menu_item__category__menu").prefetch_related("menu_item__option_groups", "selected_options__option", "selected_add_ons__add_on"))
    quantities = {}
    for line in lines:
        quantities[line.menu_item_id] = quantities.get(line.menu_item_id, 0) + line.quantity
    subtotal = 0
    for line in lines:
        line.unit_price = effective_item(line.menu_item, session.branch, quantities[line.menu_item_id])
        line.save(update_fields=["unit_price", "updated_at"])
        subtotal += line_total(line)
    if fulfillment_type == Order.Fulfillment.DELIVERY and not delivery_address.strip():
        raise ValidationError({"delivery_address": "Delivery address is required."})
    from apps.operations.services import attach_campaign, calculate_campaign
    campaign, discount = calculate_campaign(organization=session.organization, branch=session.branch, code=promotion_code, subtotal=subtotal)
    order = Order.objects.create(organization=session.organization, branch=session.branch, table=session.table, session=session, guest=session.guest, customer=session.customer, currency=cart.currency, subtotal=subtotal, discount_total=discount, total=subtotal - discount, promotion_code=campaign.code if campaign else "", fulfillment_type=fulfillment_type, delivery_address=delivery_address.strip(), idempotency_key=idempotency_key)
    snapshots = []
    for line in lines:
        options = [{"id": str(entry.option_id), "name": entry.option.name, "price_delta": entry.price_delta} for entry in line.selected_options.all()]
        add_ons = [{"id": str(entry.add_on_id), "name": entry.add_on.name, "quantity": entry.quantity, "unit_price": entry.unit_price} for entry in line.selected_add_ons.all()]
        snapshots.append(OrderLine(order=order, menu_item=line.menu_item, item_name=line.menu_item.name, quantity=line.quantity, unit_price=line.unit_price, options=options, add_ons=add_ons, note=line.note, line_total=line_total(line)))
    OrderLine.objects.bulk_create(snapshots)
    attach_campaign(order, campaign, discount)
    from apps.operations.services import consume_inventory
    consume_inventory(order)
    OrderStatusEvent.objects.create(organization=order.organization, branch=order.branch, order=order, from_status="", to_status=Order.Status.PENDING)
    NotificationOutbox.objects.create(organization=order.organization, branch=order.branch, topic="order.created", payload={"order_id": str(order.id), "status": order.status, "table_number": order.table.number, "total": order.total})
    cart.status = Cart.Status.CONVERTED
    cart.save(update_fields=["status", "updated_at"])
    return order, True

TRANSITIONS = {
    Order.Status.PENDING: {Order.Status.CONFIRMED, Order.Status.CANCELLED},
    Order.Status.CONFIRMED: {Order.Status.PREPARING, Order.Status.CANCELLED},
    Order.Status.PREPARING: {Order.Status.READY, Order.Status.CANCELLED},
    Order.Status.READY: {Order.Status.COMPLETED},
    Order.Status.COMPLETED: set(),
    Order.Status.CANCELLED: set(),
}

@transaction.atomic
def transition_order(*, order_id, organization, branch_ids, actor, target_status, expected_version, reason=""):
    order = Order.objects.select_for_update().filter(id=order_id, organization=organization, branch_id__in=branch_ids).first()
    if order is None:
        raise NotFound("Order was not found.")
    if order.version != expected_version:
        raise ValidationError({"version": "Order changed since it was loaded. Refresh and try again."}, code="version_conflict")
    if target_status not in TRANSITIONS[order.status]:
        raise ValidationError({"status": f"Transition from {order.status} to {target_status} is not allowed."})
    previous = order.status
    order.status = target_status
    order.version += 1
    order.save(update_fields=["status", "version", "updated_at"])
    OrderStatusEvent.objects.create(organization=order.organization, branch=order.branch, order=order, from_status=previous, to_status=target_status, actor=actor, reason=reason)
    NotificationOutbox.objects.create(organization=order.organization, branch=order.branch, topic="order.status_changed", payload={"order_id": str(order.id), "from_status": previous, "to_status": target_status, "version": order.version})
    return order
