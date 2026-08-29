from datetime import timedelta
import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from apps.ai.tools import execute_tool, get_food_details, recommend_menu, search_menu
from apps.branches.models import Branch
from apps.conversations.models import Conversation, Message
from apps.customers.models import TableSession
from apps.identity.models import GuestIdentity
from apps.menus.models import BranchItemAvailability, Category, Ingredient, Menu, MenuItem, MenuItemIngredient
from apps.organizations.models import Organization
from apps.tables.models import RestaurantTable

def ai_restaurant(slug="ai-cafe"):
    organization = Organization.objects.create(name="AI Cafe", slug=slug)
    branch = Branch.objects.create(organization=organization, name="Main", code="main")
    table = RestaurantTable.objects.create(organization=organization, branch=branch, number="1", qr_token_hash=(slug + "qr").ljust(64, "q"))
    guest = GuestIdentity.objects.create(expires_at=timezone.now() + timedelta(hours=5))
    raw_session_token = f"{slug}-session-token"
    session = TableSession.objects.create(organization=organization, branch=branch, table=table, guest=guest, token_hash=TableSession.hash_token(raw_session_token), expires_at=timezone.now() + timedelta(hours=4))
    menu = Menu.objects.create(organization=organization, branch=branch, name="Main", currency="IRR")
    category = Category.objects.create(organization=organization, menu=menu, name="Pizza")
    item = MenuItem.objects.create(organization=organization, category=category, name="Margherita", description="Tomato and cheese", base_price=350000, calories=650, food_type="vegetarian")
    return organization, branch, session, item, raw_session_token

@pytest.mark.django_db
def test_search_menu_returns_only_real_branch_data_and_effective_price():
    organization, branch, session, item, _ = ai_restaurant()
    BranchItemAvailability.objects.create(organization=organization, branch=branch, menu_item=item, price_override=320000)
    other_org, _, _, _, _ = ai_restaurant("other-ai-cafe")
    other_menu = Menu.objects.create(organization=other_org, name="Other")
    other_category = Category.objects.create(organization=other_org, menu=other_menu, name="Pizza")
    MenuItem.objects.create(organization=other_org, category=other_category, name="Secret Pizza", base_price=1)
    result = search_menu(session, query="Pizza")
    assert [entry["name"] for entry in result["items"]] == ["Margherita"]
    assert result["items"][0]["price"] == 320000

@pytest.mark.django_db
def test_allergen_exclusion_is_applied_by_deterministic_tool():
    organization, _, session, item, _ = ai_restaurant()
    dairy = Ingredient.objects.create(organization=organization, name="Milk", is_allergen=True, allergen_code="dairy")
    MenuItemIngredient.objects.create(menu_item=item, ingredient=dairy)
    assert search_menu(session, exclude_allergens=["dairy"])["items"] == []
    details = get_food_details(session, str(item.id))
    assert details["allergens"] == [{"name": "Milk", "code": "dairy"}]

@pytest.mark.django_db
def test_budget_recommendation_never_exceeds_per_person_budget():
    _, _, session, _, _ = ai_restaurant()
    result = recommend_menu(session, budget=600000, people=2)
    assert all(item["price"] <= 300000 for item in result["items"])

@pytest.mark.django_db
def test_unknown_tool_is_never_executed():
    _, _, session, _, _ = ai_restaurant()
    assert execute_tool("delete_all_orders", {}, session) == {"error": "tool_not_allowed"}

@pytest.mark.django_db
@override_settings(AI_PROVIDER="local", OPENAI_API_KEY="")
def test_chat_persists_conversation_but_hides_tool_messages_from_customer():
    _, _, session, _, raw_token = ai_restaurant()
    client = APIClient()
    client.credentials(HTTP_X_TABLE_SESSION=raw_token)
    response = client.post("/api/v1/customer/chat/messages/", {"content": "Pizza چی دارید؟"})
    assert response.status_code == 201
    conversation = Conversation.objects.get(session=session)
    assert conversation.expires_at == session.expires_at
    assert conversation.messages.filter(role=Message.Role.TOOL).exists()
    history = client.get("/api/v1/customer/chat/").json()["data"]["messages"]
    assert all(message["role"] != "tool" for message in history)
    assert "Margherita" in history[-1]["content"]

@pytest.mark.django_db
@override_settings(AI_PROVIDER="local", OPENAI_API_KEY="")
def test_table_session_cannot_read_another_conversation():
    _, _, first, _, first_token = ai_restaurant()
    _, _, second, _, second_token = ai_restaurant("second-ai-cafe")
    first_client = APIClient(); first_client.credentials(HTTP_X_TABLE_SESSION=first_token)
    second_client = APIClient(); second_client.credentials(HTTP_X_TABLE_SESSION=second_token)
    first_client.post("/api/v1/customer/chat/messages/", {"content": "Pizza"})
    response = second_client.get("/api/v1/customer/chat/")
    assert response.status_code == 200
    assert response.json()["data"]["id"] != str(Conversation.objects.get(session=first).id)
    assert response.json()["data"]["messages"] == []
