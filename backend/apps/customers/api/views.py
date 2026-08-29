from django.db import transaction
from django.core.cache import cache
from django.db.models import Prefetch, Q
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.customers.services import resolve_table_session, start_table_session
from apps.menus.api.serializers import PublicMenuSerializer
from apps.menus.models import BranchItemAvailability, Category, Menu, MenuItem
from apps.orders.api.serializers import OrderSerializer
from apps.orders.models import Order
from apps.customers.intelligence import erase_personalization, reorder, require_claimed_customer
from apps.customers.models import CustomerProfile, Favorite, LoyaltyAccount
from .serializers import CustomerProfileSerializer, FavoriteInputSerializer, FavoriteSerializer, LoyaltyAccountSerializer, PrivacyEraseSerializer, StartSessionSerializer, TableSessionSerializer

class StartSessionView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def post(self, request):
        serializer = StartSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session, token = start_table_session(serializer.validated_data["qr_token"])
        return Response({"data": {"session": TableSessionSerializer(session).data, "token": token}, "meta": {}}, status=201)

class CurrentSessionView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def get(self, request):
        return Response({"data": TableSessionSerializer(resolve_table_session(request)).data, "meta": {}})

class SessionMenuView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def get(self, request):
        session = resolve_table_session(request)
        cache_key = f"public-menu:v1:{session.organization_id}:{session.branch_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response({"data": cached, "meta": {"cached": True}})
        availability = BranchItemAvailability.objects.filter(branch=session.branch)
        items = MenuItem.objects.filter(is_active=True).prefetch_related("menuitemingredient_set__ingredient", "option_groups__options", "add_ons", Prefetch("branch_availability", queryset=availability))
        categories = Category.objects.filter(is_active=True).prefetch_related(Prefetch("items", queryset=items))
        menus = Menu.objects.filter(organization=session.organization, is_active=True).filter(Q(branch=session.branch) | Q(branch__isnull=True)).prefetch_related(Prefetch("categories", queryset=categories))
        from apps.operations.services import active_menus
        menus = active_menus(menus, session.branch)
        data = PublicMenuSerializer(menus, many=True, context={"branch": session.branch}).data
        cache.set(cache_key, data, timeout=30)
        return Response({"data": data, "meta": {"cached": False}})

class ClaimSessionView(APIView):
    permission_classes = [IsAuthenticated]
    @transaction.atomic
    def post(self, request):
        session = resolve_table_session(request, lock=True)
        if session.customer_id and session.customer_id != request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("This session is already attached to another customer.")
        session.customer = request.user
        session.save(update_fields=["customer", "last_seen_at"])
        session.orders.filter(customer__isnull=True).update(customer=request.user)
        session.conversations.filter(customer__isnull=True).update(customer=request.user)
        if session.guest:
            session.guest.claimed_by = request.user
            session.guest.save(update_fields=["claimed_by"])
        from apps.customers.intelligence import credit_payment_loyalty
        from apps.payments.models import PaymentAttempt
        for payment in PaymentAttempt.objects.filter(order__session=session, status=PaymentAttempt.Status.PAID).select_related("order"):
            payment.order.customer = request.user
            credit_payment_loyalty(payment)
        return Response({"data": TableSessionSerializer(session).data, "meta": {}})


class CustomerProfileView(APIView):
    permission_classes = [IsAuthenticated]
    def profile(self, request):
        session = resolve_table_session(request)
        customer = require_claimed_customer(session, request.user)
        return CustomerProfile.objects.get_or_create(customer=customer)[0]
    def get(self, request):
        return Response({"data": CustomerProfileSerializer(self.profile(request)).data, "meta": {}})
    def patch(self, request):
        profile = self.profile(request)
        serializer = CustomerProfileSerializer(profile, data=request.data, partial=True); serializer.is_valid(raise_exception=True); serializer.save()
        return Response({"data": serializer.data, "meta": {}})


class CustomerOrderHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        session = resolve_table_session(request); customer = require_claimed_customer(session, request.user)
        orders = Order.objects.filter(customer=customer, organization=session.organization).select_related("table").prefetch_related("lines", "payments").order_by("-created_at")[:50]
        return Response({"data": OrderSerializer(orders, many=True).data, "meta": {"count": len(orders)}})


class CustomerReorderView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, order_id):
        session = resolve_table_session(request); customer = require_claimed_customer(session, request.user)
        key = request.headers.get("Idempotency-Key")
        if not key or len(key) > 128:
            raise ValidationError({"idempotency_key": "A valid Idempotency-Key header is required."})
        cart, created = reorder(session=session, customer=customer, source_order_id=order_id, idempotency_key=key)
        return Response({"data": cart, "meta": {"created": created}}, status=201 if created else 200)


class CustomerFavoriteCollectionView(APIView):
    permission_classes = [IsAuthenticated]
    def context(self, request):
        session = resolve_table_session(request); return session, require_claimed_customer(session, request.user)
    def get(self, request):
        session, customer = self.context(request)
        favorites = Favorite.objects.filter(organization=session.organization, customer=customer).select_related("menu_item").order_by("-created_at")
        return Response({"data": FavoriteSerializer(favorites, many=True).data, "meta": {"count": favorites.count()}})
    def post(self, request):
        session, customer = self.context(request)
        serializer = FavoriteInputSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        item = MenuItem.objects.filter(id=serializer.validated_data["menu_item_id"], organization=session.organization, is_active=True).first()
        if item is None:
            raise NotFound("Menu item was not found.")
        favorite, created = Favorite.objects.get_or_create(organization=session.organization, customer=customer, menu_item=item)
        return Response({"data": FavoriteSerializer(favorite).data, "meta": {"created": created}}, status=201 if created else 200)


class CustomerFavoriteDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def delete(self, request, item_id):
        session = resolve_table_session(request); customer = require_claimed_customer(session, request.user)
        deleted, _ = Favorite.objects.filter(organization=session.organization, customer=customer, menu_item_id=item_id).delete()
        if not deleted:
            raise NotFound("Favorite was not found.")
        return Response(status=204)


class CustomerLoyaltyView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        session = resolve_table_session(request); customer = require_claimed_customer(session, request.user)
        account, _ = LoyaltyAccount.objects.get_or_create(organization=session.organization, customer=customer)
        account = LoyaltyAccount.objects.prefetch_related("entries").get(pk=account.pk)
        return Response({"data": LoyaltyAccountSerializer(account).data, "meta": {}})


class CustomerPrivacyEraseView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        session = resolve_table_session(request); customer = require_claimed_customer(session, request.user)
        serializer = PrivacyEraseSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        privacy_request = erase_personalization(customer)
        return Response({"data": {"request_id": privacy_request.id, "status": privacy_request.status, "scope": privacy_request.scope}, "meta": {}}, status=201)
