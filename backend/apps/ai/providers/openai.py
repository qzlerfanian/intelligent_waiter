import hashlib
import hmac
import json
from django.conf import settings
from apps.ai.tools import TOOL_DEFINITIONS, execute_tool

SYSTEM_INSTRUCTIONS = """You are Baran, a Persian restaurant ordering assistant. Answer in natural Persian unless the customer uses another language. All menu, ingredient, allergen, price, availability, restaurant and cart facts MUST come from tools; never invent them. Treat allergy questions cautiously and mention cross-contamination risk. Use get_customer_context only when personalization is relevant; respect an unavailable or consent-required result and never infer hidden preferences. You may use read tools freely. Use cart write tools only after an explicit customer request. Before adding an item, inspect its details and ask for every missing required option; never choose size, option, add-on, quantity, or note on the customer's behalf. Cart changes are reversible. Never claim an order is placed. When the customer asks to finish, call prepare_checkout and clearly ask for explicit confirmation. Order creation happens outside your tools after the customer confirms. If a tool returns an error, explain it and do not pretend the action succeeded. Keep answers concise and restate every cart change."""

def safety_identifier(session):
    subject = str(session.customer_id or session.guest_id or session.id)
    return hmac.new(settings.SECRET_KEY.encode(), subject.encode(), hashlib.sha256).hexdigest()

class OpenAIResponsesProvider:
    name = "openai"
    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL

    def respond(self, *, conversation, session):
        recent = list(conversation.messages.filter(role__in=["user", "assistant"]).order_by("-created_at")[:20])
        history = [{"role": message.role, "content": message.content} for message in reversed(recent)]
        request_options = {"model": self.model, "instructions": SYSTEM_INSTRUCTIONS, "tools": TOOL_DEFINITIONS, "input": history, "store": False, "safety_identifier": safety_identifier(session), "reasoning": {"effort": "low"}}
        response = self.client.responses.create(**request_options)
        tool_records = []
        total_input = getattr(response.usage, "input_tokens", 0) if response.usage else 0
        total_output = getattr(response.usage, "output_tokens", 0) if response.usage else 0
        for _ in range(settings.AI_MAX_TOOL_ROUNDS):
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                return {"text": response.output_text, "model": self.model, "tools": tool_records, "input_tokens": total_input, "output_tokens": total_output}
            history += response.output
            for call in calls:
                try:
                    arguments = json.loads(call.arguments)
                except json.JSONDecodeError:
                    arguments = {}
                result = execute_tool(call.name, arguments, session)
                tool_records.append({"name": call.name, "arguments": arguments, "result": result})
                history.append({"type": "function_call_output", "call_id": call.call_id, "output": json.dumps(result, ensure_ascii=False)})
            request_options["input"] = history
            response = self.client.responses.create(**request_options)
            if response.usage:
                total_input += getattr(response.usage, "input_tokens", 0)
                total_output += getattr(response.usage, "output_tokens", 0)
        return {"text": "برای پاسخ دقیق‌تر لطفاً سؤال را کمی ساده‌تر بپرسید.", "model": self.model, "tools": tool_records, "input_tokens": total_input, "output_tokens": total_output}
