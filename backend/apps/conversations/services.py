from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import APIException
from apps.ai.providers.local import LocalMenuProvider
from apps.orders.models import OrderConfirmation
from apps.orders.services import confirm_order_confirmation
from .models import Conversation, Message

def get_or_create_conversation(session):
    conversation, _ = Conversation.objects.get_or_create(session=session, status=Conversation.Status.ACTIVE, defaults={"organization": session.organization, "branch": session.branch, "guest": session.guest, "customer": session.customer, "expires_at": session.expires_at})
    return conversation

def get_provider():
    use_openai = settings.AI_PROVIDER == "openai" or (settings.AI_PROVIDER == "auto" and bool(settings.OPENAI_API_KEY))
    if use_openai:
        from apps.ai.providers.openai import OpenAIResponsesProvider
        return OpenAIResponsesProvider()
    return LocalMenuProvider()

def send_message(*, session, content):
    conversation = get_or_create_conversation(session)
    Message.objects.create(conversation=conversation, role=Message.Role.USER, content=content)
    pending = OrderConfirmation.objects.filter(session=session, status=OrderConfirmation.Status.PENDING).order_by("-created_at").first()
    normalized = " ".join(content.casefold().replace("‌", " ").replace(".", "").replace("!", "").replace("؟", "").replace("،", "").split())
    affirmative = {"بله", "آره", "تایید", "تأیید", "تایید میکنم", "تأیید میکنم", "تایید می کنم", "تأیید می کنم", "ثبت کن", "سفارش رو ثبت کن", "بله ثبت کن"}
    negative = {"نه", "خیر", "لغو", "لغو کن", "فعلا نه", "فعلاً نه"}
    if pending and normalized in affirmative:
        order = confirm_order_confirmation(session=session, confirmation_id=pending.id)
        assistant = Message.objects.create(conversation=conversation, role=Message.Role.ASSISTANT, content=f"سفارش با شماره پیگیری {str(order.id)[:8]} ثبت شد و به رستوران فرستاده شد.", metadata={"provider": "confirmation-gateway", "actions": [{"type": "order_confirmed", "order_id": str(order.id)}]})
        return conversation, assistant
    if pending and normalized in negative:
        pending.status = OrderConfirmation.Status.CANCELLED
        pending.save(update_fields=["status"])
        assistant = Message.objects.create(conversation=conversation, role=Message.Role.ASSISTANT, content="ثبت سفارش لغو شد؛ سبدت بدون تغییر باقی مانده است.", metadata={"provider": "confirmation-gateway"})
        return conversation, assistant
    provider = get_provider()
    try:
        result = provider.respond(conversation=conversation, session=session)
    except Exception as exc:
        raise AIServiceUnavailable() from exc
    with transaction.atomic():
        for record in result["tools"]:
            Message.objects.create(conversation=conversation, role=Message.Role.TOOL, tool_name=record["name"], metadata={"arguments": record["arguments"], "result": record["result"]})
        actions = []
        for record in result["tools"]:
            tool_result = record.get("result", {})
            if isinstance(tool_result, dict) and tool_result.get("action"):
                action = {"type": tool_result["action"]}
                if tool_result.get("confirmation_id"):
                    action.update({"confirmation_id": tool_result["confirmation_id"], "cart": tool_result.get("cart"), "expires_at": tool_result.get("expires_at")})
                actions.append(action)
        assistant = Message.objects.create(conversation=conversation, role=Message.Role.ASSISTANT, content=result["text"], metadata={"provider": provider.name, "model": result["model"], "actions": actions}, input_tokens=result["input_tokens"], output_tokens=result["output_tokens"])
        conversation.provider = provider.name
        conversation.model = result["model"]
        conversation.customer = session.customer
        conversation.save(update_fields=["provider", "model", "customer", "updated_at"])
    return conversation, assistant

class AIServiceUnavailable(APIException):
    status_code = 503
    default_detail = "The menu assistant is temporarily unavailable."
    default_code = "ai_service_unavailable"
