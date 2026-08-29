from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from apps.customers.services import resolve_table_session
from apps.orders.models import Cart, CartLine, Order
from apps.orders.services import add_cart_line, confirm_cart, get_active_cart, remove_cart_line, update_cart_line
from .serializers import AddCartLineSerializer, CartLineSerializer, CartSerializer, ConfirmOrderSerializer, OrderSerializer, UpdateCartLineSerializer

def loaded_cart(session):
    return Cart.objects.prefetch_related("lines__menu_item", "lines__selected_options__option", "lines__selected_add_ons__add_on").filter(session=session, status=Cart.Status.ACTIVE).first()

class CartView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def get(self, request):
        session = resolve_table_session(request)
        cart = loaded_cart(session) or get_active_cart(session)
        return Response({"data": CartSerializer(cart).data, "meta": {}})

class CartLineCollectionView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def post(self, request):
        session = resolve_table_session(request)
        serializer = AddCartLineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        line = add_cart_line(session=session, **serializer.validated_data)
        line = CartLine.objects.select_related("menu_item").prefetch_related("selected_options__option", "selected_add_ons__add_on").get(pk=line.pk)
        return Response({"data": CartLineSerializer(line).data, "meta": {}}, status=201)

class CartLineDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def get_line(self, request, line_id):
        session = resolve_table_session(request)
        line = CartLine.objects.filter(id=line_id, cart__session=session, cart__status=Cart.Status.ACTIVE).first()
        if line is None:
            raise NotFound("Cart line was not found.")
        return line
    def patch(self, request, line_id):
        session = resolve_table_session(request)
        self.get_line(request, line_id)
        serializer = UpdateCartLineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        line = update_cart_line(session=session, line_id=line_id, **serializer.validated_data)
        line = CartLine.objects.select_related("menu_item").prefetch_related("selected_options__option", "selected_add_ons__add_on").get(pk=line.pk)
        return Response({"data": CartLineSerializer(line).data, "meta": {}})
    def delete(self, request, line_id):
        session = resolve_table_session(request)
        self.get_line(request, line_id)
        remove_cart_line(session=session, line_id=line_id)
        return Response(status=204)

class ConfirmOrderView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "checkout"
    @transaction.atomic
    def post(self, request):
        key = request.headers.get("Idempotency-Key")
        if not key or len(key) > 128:
            raise ValidationError({"idempotency_key": "A valid Idempotency-Key header is required."})
        serializer = ConfirmOrderSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        session = resolve_table_session(request, lock=True)
        order, created = confirm_cart(session=session, idempotency_key=key, **serializer.validated_data)
        order = Order.objects.select_related("table").prefetch_related("lines", "payments").get(pk=order.pk)
        return Response({"data": OrderSerializer(order).data, "meta": {"created": created}}, status=201 if created else 200)

class OrderDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def get(self, request, order_id):
        session = resolve_table_session(request)
        order = Order.objects.select_related("table").prefetch_related("lines", "payments").filter(id=order_id, session=session).first()
        if order is None:
            raise NotFound("Order was not found.")
        return Response({"data": OrderSerializer(order).data, "meta": {}})
