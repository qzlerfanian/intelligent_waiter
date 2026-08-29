from decimal import Decimal
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Campaign, CampaignRedemption, MenuSchedule, RecipeComponent, StockItem, StockMovement

def active_menus(queryset, branch, now=None):
    now = now or timezone.localtime()
    # JSON containment is not available on SQLite (used by local tests).
    schedules = MenuSchedule.objects.filter(organization=branch.organization, branch=branch, is_active=True, starts_at__lte=now.time(), ends_at__gt=now.time())
    scheduled_ids = [schedule.menu_id for schedule in schedules if now.weekday() in schedule.weekdays]
    menus_with_schedules = MenuSchedule.objects.filter(branch=branch, is_active=True).values_list("menu_id", flat=True)
    return queryset.filter(~models.Q(id__in=menus_with_schedules) | models.Q(id__in=scheduled_ids))

def calculate_campaign(*, organization, branch, code, subtotal):
    if not code:
        return None, 0
    now = timezone.now()
    campaign = Campaign.objects.select_for_update().filter(organization=organization, code__iexact=code.strip(), is_active=True, starts_at__lte=now, ends_at__gt=now).filter(models.Q(branch=branch) | models.Q(branch__isnull=True)).first()
    if campaign is None or subtotal < campaign.minimum_order:
        raise ValidationError({"promotion_code": "Promotion code is invalid or not applicable."})
    if campaign.usage_limit is not None and campaign.redemptions.count() >= campaign.usage_limit:
        raise ValidationError({"promotion_code": "Promotion usage limit has been reached."})
    discount = subtotal * campaign.value // 100 if campaign.kind == Campaign.Kind.PERCENT else campaign.value
    if campaign.maximum_discount is not None:
        discount = min(discount, campaign.maximum_discount)
    return campaign, min(discount, subtotal)

@transaction.atomic
def consume_inventory(order):
    requirements = {}
    for line in order.lines.all():
        if not line.menu_item_id:
            continue
        for component in RecipeComponent.objects.filter(menu_item_id=line.menu_item_id, stock_item__branch=order.branch).select_related("stock_item"):
            requirements[component.stock_item_id] = requirements.get(component.stock_item_id, Decimal("0")) + component.quantity * line.quantity
    stocks = {item.id: item for item in StockItem.objects.select_for_update().filter(id__in=requirements)}
    for stock_id, required in requirements.items():
        if stocks[stock_id].quantity < required:
            raise ValidationError({"inventory": f"Insufficient stock for {stocks[stock_id].ingredient.name}."})
    for stock_id, required in requirements.items():
        StockItem.objects.filter(pk=stock_id).update(quantity=F("quantity") - required)
        StockMovement.objects.create(stock_item=stocks[stock_id], order=order, delta=-required, reason="order_consumption")

def attach_campaign(order, campaign, discount):
    if campaign:
        CampaignRedemption.objects.create(campaign=campaign, order=order, discount_amount=discount)
