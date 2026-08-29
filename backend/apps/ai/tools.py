from django.db.models import Q
from rest_framework.exceptions import APIException
from apps.menus.models import BranchItemAvailability, MenuItem
from apps.orders.services import add_cart_line, get_active_cart, prepare_order_confirmation, remove_cart_line, serialize_cart, update_cart_line
from apps.customers.models import CustomerProfile, Favorite
from apps.orders.models import Order

TOOL_DEFINITIONS = [
    {"type": "function", "name": "search_menu", "description": "Search the real menu for available foods matching customer constraints.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "max_price": {"type": ["integer", "null"], "minimum": 0}, "max_calories": {"type": ["integer", "null"], "minimum": 0}, "food_type": {"type": ["string", "null"], "enum": ["regular", "vegetarian", "vegan", None]}, "exclude_allergens": {"type": "array", "items": {"type": "string"}}}, "required": ["query", "max_price", "max_calories", "food_type", "exclude_allergens"], "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "get_food_details", "description": "Get trusted details, ingredients, allergens, options, add-ons, price and availability for one menu item.", "parameters": {"type": "object", "properties": {"item_id": {"type": "string"}}, "required": ["item_id"], "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "recommend_menu", "description": "Return deterministic menu candidates for a budget and number of people.", "parameters": {"type": "object", "properties": {"budget": {"type": "integer", "minimum": 0}, "people": {"type": "integer", "minimum": 1, "maximum": 20}, "food_type": {"type": ["string", "null"], "enum": ["regular", "vegetarian", "vegan", None]}, "max_calories": {"type": ["integer", "null"], "minimum": 0}, "exclude_allergens": {"type": "array", "items": {"type": "string"}}}, "required": ["budget", "people", "food_type", "max_calories", "exclude_allergens"], "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "get_restaurant_info", "description": "Get the current restaurant, branch and table information.", "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "get_cart", "description": "Read the customer's current cart and deterministic total. Use before summarizing or preparing checkout.", "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "add_item_to_cart", "description": "Add an item only after the customer explicitly asks for it and all required options are known. This is reversible and does not place an order.", "parameters": {"type": "object", "properties": {"menu_item_id": {"type": "string"}, "quantity": {"type": "integer", "minimum": 1, "maximum": 50}, "option_ids": {"type": "array", "items": {"type": "string"}}, "add_ons": {"type": "array", "items": {"type": "object", "properties": {"add_on_id": {"type": "string"}, "quantity": {"type": "integer", "minimum": 1}}, "required": ["add_on_id", "quantity"], "additionalProperties": False}}, "note": {"type": "string", "maxLength": 500}}, "required": ["menu_item_id", "quantity", "option_ids", "add_ons", "note"], "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "update_cart_item", "description": "Update quantity or note for an existing cart line after an explicit customer request.", "parameters": {"type": "object", "properties": {"line_id": {"type": "string"}, "quantity": {"type": ["integer", "null"], "minimum": 1, "maximum": 50}, "note": {"type": ["string", "null"], "maxLength": 500}}, "required": ["line_id", "quantity", "note"], "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "remove_item_from_cart", "description": "Remove one cart line after the customer explicitly requests removal.", "parameters": {"type": "object", "properties": {"line_id": {"type": "string"}}, "required": ["line_id"], "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "prepare_checkout", "description": "Create a short-lived checkout preview after the customer asks to finish. This never creates an order; explicit customer confirmation is still required.", "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "get_customer_context", "description": "Get the signed-in customer's consented dietary preferences, favorites and recent orders for personalization. Returns unavailable unless explicit AI personalization consent is active.", "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}, "strict": True},
]

def _base_items(session):
    return MenuItem.objects.filter(organization=session.organization, category__menu__is_active=True, category__is_active=True, is_active=True, is_available=True).filter(Q(category__menu__branch=session.branch) | Q(category__menu__branch__isnull=True)).select_related("category__menu").prefetch_related("menuitemingredient_set__ingredient", "option_groups__options", "add_ons")

def _effective(item, branch):
    override = BranchItemAvailability.objects.filter(branch=branch, menu_item=item).first()
    available = override is None or (override.is_available and (override.stock_quantity is None or override.stock_quantity > 0))
    price = override.price_override if override and override.price_override is not None else (item.discount_price if item.discount_price is not None else item.base_price)
    return available, price

def _allergens(item):
    return [{"name": link.ingredient.name, "code": link.ingredient.allergen_code} for link in item.menuitemingredient_set.all() if link.ingredient.is_allergen]

def _summary(item, branch):
    available, price = _effective(item, branch)
    return {"id": str(item.id), "name": item.name, "description": item.description, "price": price, "currency": item.category.menu.currency, "available": available, "calories": item.calories, "food_type": item.food_type, "preparation_minutes": item.preparation_minutes, "spice_level": item.spice_level, "allergens": _allergens(item), "chef_recommended": item.is_chef_recommended}

def search_menu(session, query="", max_price=None, max_calories=None, food_type=None, exclude_allergens=None):
    items = _base_items(session)
    if query:
        items = items.filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(category__name__icontains=query) | Q(menuitemingredient__ingredient__name__icontains=query)).distinct()
    if max_calories is not None:
        items = items.filter(calories__lte=max_calories)
    if food_type:
        items = items.filter(food_type=food_type)
    excluded = {value.casefold() for value in (exclude_allergens or [])}
    results = []
    for item in items[:40]:
        summary = _summary(item, session.branch)
        item_allergens = {value.casefold() for allergen in summary["allergens"] for value in (allergen["name"], allergen["code"]) if value}
        if summary["available"] and (max_price is None or summary["price"] <= max_price) and not excluded.intersection(item_allergens):
            results.append(summary)
        if len(results) == 12:
            break
    return {"items": results, "count": len(results), "constraints_applied": {"max_price": max_price, "max_calories": max_calories, "food_type": food_type, "excluded_allergens": list(excluded)}}

def get_food_details(session, item_id):
    item = _base_items(session).filter(id=item_id).first()
    if item is None:
        return {"found": False}
    result = _summary(item, session.branch)
    result.update({"found": True, "ingredients": [{"name": link.ingredient.name, "removable": link.is_removable} for link in item.menuitemingredient_set.all()], "option_groups": [{"name": group.name, "required": group.is_required, "min": group.min_selections, "max": group.max_selections, "options": [{"id": str(option.id), "name": option.name, "price_delta": option.price_delta, "available": option.is_available} for option in group.options.all()]} for group in item.option_groups.all()], "add_ons": [{"id": str(add_on.id), "name": add_on.name, "price": add_on.price, "max_quantity": add_on.max_quantity, "available": add_on.is_available} for add_on in item.add_ons.all()]})
    return result

def recommend_menu(session, budget, people, food_type=None, max_calories=None, exclude_allergens=None):
    per_person = budget // people
    result = search_menu(session, query="", max_price=per_person, max_calories=max_calories, food_type=food_type, exclude_allergens=exclude_allergens)
    result.update({"budget": budget, "people": people, "per_person_budget": per_person, "note": "Candidates fit the per-person budget; totals remain deterministic at cart calculation."})
    return result

def get_restaurant_info(session):
    return {"organization": session.organization.name, "branch": session.branch.name, "branch_code": session.branch.code, "address": session.branch.address, "table_number": session.table.number, "currency_note": "Each menu result includes its actual currency."}

def get_cart(session):
    return serialize_cart(get_active_cart(session))

def add_item_to_cart(session, menu_item_id, quantity, option_ids, add_ons, note=""):
    add_cart_line(session=session, menu_item_id=menu_item_id, quantity=quantity, option_ids=option_ids, add_ons=add_ons, note=note)
    return {"cart": get_cart(session), "action": "cart_changed"}

def update_cart_item(session, line_id, quantity=None, note=None):
    update_cart_line(session=session, line_id=line_id, quantity=quantity, note=note)
    return {"cart": get_cart(session), "action": "cart_changed"}

def remove_item_from_cart(session, line_id):
    remove_cart_line(session=session, line_id=line_id)
    return {"cart": get_cart(session), "action": "cart_changed"}

def prepare_checkout(session):
    confirmation, cart = prepare_order_confirmation(session=session)
    return {"confirmation_id": str(confirmation.id), "expires_at": confirmation.expires_at.isoformat(), "cart": cart, "action": "confirm_order", "requires_explicit_customer_confirmation": True}

def get_customer_context(session):
    if not session.customer_id:
        return {"available": False, "reason": "customer_not_signed_in"}
    profile = CustomerProfile.objects.filter(customer_id=session.customer_id, ai_personalization_consent=True).first()
    if profile is None:
        return {"available": False, "reason": "personalization_consent_required"}
    favorites = list(Favorite.objects.filter(customer_id=session.customer_id, organization=session.organization).values_list("menu_item__name", flat=True)[:10])
    recent = Order.objects.filter(customer_id=session.customer_id, organization=session.organization).prefetch_related("lines").order_by("-created_at")[:5]
    return {"available": True, "diet": profile.diet, "allergen_codes": profile.allergen_codes, "disliked_ingredients": profile.disliked_ingredients, "spice_preference": profile.spice_preference, "favorites": favorites, "recent_orders": [[{"name": line.item_name, "quantity": line.quantity} for line in order.lines.all()] for order in recent]}

TOOL_HANDLERS = {"search_menu": search_menu, "get_food_details": get_food_details, "recommend_menu": recommend_menu, "get_restaurant_info": get_restaurant_info, "get_cart": get_cart, "add_item_to_cart": add_item_to_cart, "update_cart_item": update_cart_item, "remove_item_from_cart": remove_item_from_cart, "prepare_checkout": prepare_checkout, "get_customer_context": get_customer_context}

def execute_tool(name, arguments, session):
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return {"error": "tool_not_allowed"}
    try:
        return handler(session=session, **arguments)
    except APIException as exc:
        return {"error": getattr(exc, "default_code", "tool_validation_error"), "details": exc.detail}
    except (TypeError, ValueError):
        return {"error": "invalid_tool_arguments"}
