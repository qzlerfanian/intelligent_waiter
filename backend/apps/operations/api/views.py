from django.db import transaction
from django.db.models import F, Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from apps.customers.services import resolve_table_session
from apps.operations.models import Campaign, MenuSchedule, RecipeComponent, Reservation, StockItem, StockMovement
from shared.tenancy.permissions import CanManageRestaurantResources, HasTenantContext
from shared.tenancy.scopes import accessible_branch_ids
from .serializers import CampaignSerializer, CustomerReservationSerializer, MenuScheduleSerializer, RecipeComponentSerializer, ReservationSerializer, StockAdjustmentSerializer, StockItemSerializer

class ScopedViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasTenantContext, CanManageRestaurantResources]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    branch_field = "branch_id"
    def scoped(self, queryset):
        ids = accessible_branch_ids(self.request.user, self.request.organization)
        return queryset if ids is None else queryset.filter(**{f"{self.branch_field}__in": ids})
    def perform_create(self, serializer): serializer.save(organization=self.request.organization)

class CampaignViewSet(ScopedViewSet):
    serializer_class = CampaignSerializer
    def get_queryset(self): return self.scoped(Campaign.objects.filter(organization=self.request.organization))

class MenuScheduleViewSet(ScopedViewSet):
    serializer_class = MenuScheduleSerializer
    def get_queryset(self): return self.scoped(MenuSchedule.objects.filter(organization=self.request.organization))

class StockItemViewSet(ScopedViewSet):
    serializer_class = StockItemSerializer
    def get_queryset(self): return self.scoped(StockItem.objects.filter(organization=self.request.organization).select_related("ingredient", "branch"))
    @transaction.atomic
    def perform_create(self, serializer):
        stock = serializer.save(organization=self.request.organization)
        if stock.quantity:
            StockMovement.objects.create(stock_item=stock, delta=stock.quantity, reason="initial_stock", actor=self.request.user)
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def adjust(self, request, pk=None):
        stock = StockItem.objects.select_for_update().get(pk=self.get_object().pk)
        serializer = StockAdjustmentSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        if stock.quantity + serializer.validated_data["delta"] < 0: raise ValidationError({"delta": "Stock cannot become negative."})
        StockItem.objects.filter(pk=stock.pk).update(quantity=F("quantity") + serializer.validated_data["delta"])
        StockMovement.objects.create(stock_item=stock, delta=serializer.validated_data["delta"], reason=serializer.validated_data["reason"], actor=request.user)
        stock.refresh_from_db(); return Response({"data": self.get_serializer(stock).data, "meta": {}})

class RecipeComponentViewSet(ScopedViewSet):
    serializer_class = RecipeComponentSerializer
    branch_field = "stock_item__branch_id"
    def get_queryset(self): return self.scoped(RecipeComponent.objects.filter(menu_item__organization=self.request.organization).select_related("menu_item", "stock_item"))
    def perform_create(self, serializer): serializer.save()

class ReservationViewSet(ScopedViewSet):
    serializer_class = ReservationSerializer
    def get_queryset(self): return self.scoped(Reservation.objects.filter(organization=self.request.organization).select_related("branch", "table", "customer").order_by("starts_at"))

class CustomerReservationView(APIView):
    permission_classes = [AllowAny]; authentication_classes = []
    throttle_classes = [ScopedRateThrottle]; throttle_scope = "reservation"
    def post(self, request):
        session = resolve_table_session(request); serializer = CustomerReservationSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        overlap = Reservation.objects.filter(branch=session.branch, status__in=["pending", "confirmed"], starts_at__lt=data["starts_at"] + __import__("datetime").timedelta(minutes=data["duration_minutes"]), starts_at__gt=data["starts_at"] - __import__("datetime").timedelta(minutes=240)).count()
        capacity = session.branch.tables.filter(is_active=True).count()
        if overlap >= capacity: raise ValidationError({"starts_at": "No table capacity is available for this time."})
        reservation = Reservation.objects.create(organization=session.organization, branch=session.branch, customer=session.customer, **data)
        return Response({"data": ReservationSerializer(reservation).data, "meta": {}}, status=201)
