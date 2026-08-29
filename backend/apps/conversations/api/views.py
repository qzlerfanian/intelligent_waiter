from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from apps.customers.services import resolve_table_session
from apps.conversations.services import get_or_create_conversation, send_message
from apps.orders.api.serializers import OrderSerializer
from apps.orders.models import Order
from apps.orders.services import confirm_order_confirmation
from .serializers import ConversationSerializer, MessageSerializer, SendMessageSerializer

class ConversationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def get(self, request):
        session = resolve_table_session(request)
        conversation = get_or_create_conversation(session)
        return Response({"data": ConversationSerializer(conversation).data, "meta": {}})

class MessageView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "chat"
    def post(self, request):
        session = resolve_table_session(request)
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation, message = send_message(session=session, content=serializer.validated_data["content"])
        return Response({"data": {"conversation_id": conversation.id, "message": MessageSerializer(message).data}, "meta": {"provider": conversation.provider, "model": conversation.model}}, status=201)

class ConfirmCheckoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def post(self, request, confirmation_id):
        session = resolve_table_session(request)
        order = confirm_order_confirmation(session=session, confirmation_id=confirmation_id)
        order = Order.objects.select_related("table").prefetch_related("lines").get(pk=order.pk)
        return Response({"data": OrderSerializer(order).data, "meta": {"confirmed_by": "explicit_customer_action"}}, status=201)
