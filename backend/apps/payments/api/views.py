from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle

from apps.customers.services import resolve_table_session
from apps.orders.models import Order
from apps.payments.models import Invoice, PaymentAttempt
from apps.payments.services import create_payment, mock_gateway_confirm

from .serializers import CreatePaymentSerializer, InvoiceSerializer, MockConfirmSerializer, PaymentSerializer


class CustomerPaymentCollectionView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "payment"
    def get(self, request):
        session = resolve_table_session(request)
        payments = PaymentAttempt.objects.filter(order__session=session).order_by("-created_at")
        return Response({"data": PaymentSerializer(payments, many=True).data, "meta": {"count": payments.count()}})
    def post(self, request):
        session = resolve_table_session(request)
        key = request.headers.get("Idempotency-Key")
        if not key or len(key) > 128:
            raise ValidationError({"idempotency_key": "A valid Idempotency-Key header is required."})
        serializer = CreatePaymentSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        order = Order.objects.filter(id=serializer.validated_data["order_id"], session=session).first()
        if order is None:
            raise NotFound("Order was not found.")
        payment, created = create_payment(order=order, method=serializer.validated_data["method"], idempotency_key=key)
        return Response({"data": PaymentSerializer(payment).data, "meta": {"created": created}}, status=201 if created else 200)


class MockGatewayConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def post(self, request, payment_id):
        session = resolve_table_session(request)
        serializer = MockConfirmSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        payment, changed = mock_gateway_confirm(session=session, payment_id=payment_id, gateway_token=serializer.validated_data["token"])
        return Response({"data": PaymentSerializer(payment).data, "meta": {"verified": True, "changed": changed}})


class CustomerInvoiceView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def get(self, request, order_id):
        session = resolve_table_session(request)
        invoice = Invoice.objects.filter(order_id=order_id, order__session=session).first()
        if invoice is None:
            raise NotFound("Invoice was not found.")
        return Response({"data": InvoiceSerializer(invoice).data, "meta": {}})
