from django.db import models
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.branches.models import Branch
from apps.orders.models import Order
from apps.orders.services import transition_order
from apps.organizations.models import Role
from apps.payments.services import create_payment, mark_payment_paid
from shared.tenancy.permissions import HasTenantContext
from shared.tenancy.scopes import accessible_branch_ids
from .permissions import IsRestaurantStaff
from .serializers import CollectPaymentSerializer, StaffOrderSerializer, TransitionSerializer

def scoped_branch_ids(request):
    allowed = accessible_branch_ids(request.user, request.organization)
    if allowed is None:
        allowed = list(Branch.objects.filter(organization=request.organization, is_active=True).values_list("id", flat=True))
    requested = request.query_params.get("branch")
    if requested:
        allowed = [branch_id for branch_id in allowed if str(branch_id) == requested]
    return allowed

def visible_statuses(request):
    role = request.staff_membership.role
    if role in (Role.CHEF, Role.KITCHEN_STAFF):
        return [Order.Status.CONFIRMED, Order.Status.PREPARING, Order.Status.READY]
    if role == Role.WAITER:
        return [Order.Status.CONFIRMED, Order.Status.READY, Order.Status.COMPLETED]
    return list(Order.Status.values)

class StaffContextView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext, IsRestaurantStaff]
    def get(self, request):
        branch_ids = scoped_branch_ids(request)
        branches = Branch.objects.filter(id__in=branch_ids).values("id", "name", "code")
        return Response({"data": {"user": {"id": request.user.id, "display_name": request.user.display_name, "email": request.user.email}, "organization": {"id": request.organization.id, "name": request.organization.name}, "role": request.staff_membership.role, "branches": list(branches)}, "meta": {}})

class StaffOrderListView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext, IsRestaurantStaff]
    def get(self, request):
        branch_ids = scoped_branch_ids(request)
        queryset = Order.objects.filter(organization=request.organization, branch_id__in=branch_ids, status__in=visible_statuses(request)).select_related("branch", "table").prefetch_related("lines", "status_events__actor", "payments").order_by("created_at")
        statuses = request.query_params.get("status")
        if statuses:
            queryset = queryset.filter(status__in=statuses.split(","))
        since_version = request.query_params.get("updated_after")
        if since_version:
            queryset = queryset.filter(updated_at__gt=since_version)
        return Response({"data": StaffOrderSerializer(queryset[:200], many=True).data, "meta": {"count": queryset.count()}})

class StaffOrderDetailView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext, IsRestaurantStaff]
    def get_order(self, request, order_id):
        order = Order.objects.filter(id=order_id, organization=request.organization, branch_id__in=scoped_branch_ids(request), status__in=visible_statuses(request)).select_related("branch", "table").prefetch_related("lines", "status_events__actor", "payments").first()
        if order is None:
            from rest_framework.exceptions import NotFound
            raise NotFound("Order was not found.")
        return order
    def get(self, request, order_id):
        return Response({"data": StaffOrderSerializer(self.get_order(request, order_id)).data, "meta": {}})
    def patch(self, request, order_id):
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = serializer.validated_data["status"]
        role = request.staff_membership.role
        allowed = {
            Order.Status.CONFIRMED: {Role.OWNER, Role.ADMIN, Role.BRANCH_MANAGER, Role.CASHIER},
            Order.Status.PREPARING: {Role.OWNER, Role.ADMIN, Role.BRANCH_MANAGER, Role.CHEF, Role.KITCHEN_STAFF},
            Order.Status.READY: {Role.OWNER, Role.ADMIN, Role.BRANCH_MANAGER, Role.CHEF, Role.KITCHEN_STAFF},
            Order.Status.COMPLETED: {Role.OWNER, Role.ADMIN, Role.BRANCH_MANAGER, Role.CASHIER, Role.WAITER},
            Order.Status.CANCELLED: {Role.OWNER, Role.ADMIN, Role.BRANCH_MANAGER, Role.CASHIER},
        }
        if role not in allowed.get(target, set()):
            raise PermissionDenied("Your role cannot perform this transition.")
        order = transition_order(order_id=order_id, organization=request.organization, branch_ids=scoped_branch_ids(request), actor=request.user, target_status=target, expected_version=serializer.validated_data["version"], reason=serializer.validated_data["reason"])
        order = Order.objects.select_related("branch", "table").prefetch_related("lines", "status_events__actor", "payments").get(pk=order.pk)
        return Response({"data": StaffOrderSerializer(order).data, "meta": {}})

class StaffSummaryView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext, IsRestaurantStaff]
    def get(self, request):
        counts = Order.objects.filter(organization=request.organization, branch_id__in=scoped_branch_ids(request), status__in=visible_statuses(request)).values("status").annotate(count=Count("id"))
        return Response({"data": {entry["status"]: entry["count"] for entry in counts}, "meta": {}})

class StaffAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext, IsRestaurantStaff]
    def get(self, request):
        branch_ids = scoped_branch_ids(request); today = timezone.localdate(); start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
        orders = Order.objects.filter(organization=request.organization, branch_id__in=branch_ids, created_at__gte=start)
        from apps.payments.models import PaymentAttempt
        from apps.operations.models import Reservation, StockItem
        revenue = PaymentAttempt.objects.filter(organization=request.organization, branch_id__in=branch_ids, status=PaymentAttempt.Status.PAID, paid_at__gte=start).aggregate(total=Sum("amount"))["total"] or 0
        top_items = orders.values("lines__item_name").annotate(quantity=Sum("lines__quantity")).order_by("-quantity")[:5]
        low_stock = StockItem.objects.filter(organization=request.organization, branch_id__in=branch_ids, quantity__lte=models.F("reorder_level")).select_related("ingredient", "branch")[:20]
        return Response({"data": {"date": today, "revenue": revenue, "orders": orders.count(), "average_order": (orders.aggregate(value=Sum("total"))["value"] or 0) // max(orders.count(), 1), "top_items": list(top_items), "low_stock": [{"id": item.id, "ingredient": item.ingredient.name, "branch": item.branch.name, "quantity": item.quantity, "unit": item.unit} for item in low_stock], "reservations": Reservation.objects.filter(organization=request.organization, branch_id__in=branch_ids, starts_at__gte=start, starts_at__lt=start + timezone.timedelta(days=1)).count()}, "meta": {}})

class StaffCollectPaymentView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext, IsRestaurantStaff]
    def post(self, request, order_id):
        if request.staff_membership.role not in {Role.OWNER, Role.ADMIN, Role.BRANCH_MANAGER, Role.CASHIER}:
            raise PermissionDenied("Your role cannot collect payments.")
        key = request.headers.get("Idempotency-Key")
        if not key or len(key) > 128:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"idempotency_key": "A valid Idempotency-Key header is required."})
        order = Order.objects.filter(id=order_id, organization=request.organization, branch_id__in=scoped_branch_ids(request)).first()
        if order is None:
            from rest_framework.exceptions import NotFound
            raise NotFound("Order was not found.")
        serializer = CollectPaymentSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        payment, _ = create_payment(order=order, method=serializer.validated_data["method"], idempotency_key=key, actor=request.user)
        payment, changed = mark_payment_paid(payment=payment, source="staff_collection", actor=request.user)
        order = Order.objects.select_related("branch", "table").prefetch_related("lines", "status_events__actor", "payments").get(pk=order.pk)
        return Response({"data": StaffOrderSerializer(order).data, "meta": {"payment_id": payment.id, "changed": changed}})
