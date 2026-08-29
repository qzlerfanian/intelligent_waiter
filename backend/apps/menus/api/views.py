from django.db.models import Prefetch, Q
from django.core.cache import cache
from rest_framework import viewsets
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.menus.models import AddOn, BranchItemAvailability, Category, Ingredient, Menu, MenuItem, Option, OptionGroup
from apps.tables.models import RestaurantTable
from shared.tenancy.permissions import CanManageRestaurantResources, HasTenantContext
from shared.tenancy.scopes import accessible_branch_ids
from .serializers import AddOnSerializer, AvailabilitySerializer, CategorySerializer, IngredientSerializer, MenuItemSerializer, MenuSerializer, OptionGroupSerializer, OptionSerializer, PublicMenuSerializer

class TenantModelViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasTenantContext, CanManageRestaurantResources]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    branch_relation = None
    def validate_branch_scope(self, serializer):
        if self.branch_relation is None:
            return
        value = serializer.validated_data.get(self.branch_relation)
        if value is None and serializer.instance is not None:
            value = getattr(serializer.instance, self.branch_relation)
        branch = value
        for attribute in getattr(self, "branch_path", ()):
            branch = getattr(branch, attribute)
        branch_ids = accessible_branch_ids(self.request.user, self.request.organization)
        if branch_ids is not None and (branch is None or branch.id not in branch_ids):
            raise PermissionDenied("You cannot manage resources for this branch.")
    def perform_create(self, serializer):
        self.validate_branch_scope(serializer)
        serializer.save(organization=self.request.organization)
    def perform_update(self, serializer):
        self.validate_branch_scope(serializer)
        serializer.save()

class MenuViewSet(TenantModelViewSet):
    serializer_class = MenuSerializer
    branch_relation = "branch"
    def get_queryset(self):
        queryset = Menu.objects.filter(organization=self.request.organization)
        branch_ids = accessible_branch_ids(self.request.user, self.request.organization)
        return queryset if branch_ids is None else queryset.filter(branch_id__in=branch_ids)
    def perform_create(self, serializer):
        branch = serializer.validated_data.get("branch")
        branch_ids = accessible_branch_ids(self.request.user, self.request.organization)
        if branch_ids is not None and (branch is None or branch.id not in branch_ids):
            raise PermissionDenied("Branch managers can only create menus for assigned branches.")
        super().perform_create(serializer)

class CategoryViewSet(TenantModelViewSet):
    serializer_class = CategorySerializer
    branch_relation = "menu"
    branch_path = ("branch",)
    def get_queryset(self):
        queryset = Category.objects.filter(organization=self.request.organization).select_related("menu")
        branch_ids = accessible_branch_ids(self.request.user, self.request.organization)
        return queryset if branch_ids is None else queryset.filter(menu__branch_id__in=branch_ids)

class IngredientViewSet(TenantModelViewSet):
    serializer_class = IngredientSerializer
    def get_queryset(self):
        return Ingredient.objects.filter(organization=self.request.organization)

class MenuItemViewSet(TenantModelViewSet):
    serializer_class = MenuItemSerializer
    branch_relation = "category"
    branch_path = ("menu", "branch")
    def get_queryset(self):
        queryset = MenuItem.objects.filter(organization=self.request.organization).select_related("category__menu").prefetch_related("menuitemingredient_set__ingredient", "option_groups__options", "add_ons")
        branch_ids = accessible_branch_ids(self.request.user, self.request.organization)
        return queryset if branch_ids is None else queryset.filter(category__menu__branch_id__in=branch_ids)

class OptionGroupViewSet(TenantModelViewSet):
    serializer_class = OptionGroupSerializer
    branch_relation = "menu_item"
    branch_path = ("category", "menu", "branch")
    def get_queryset(self):
        queryset = OptionGroup.objects.filter(organization=self.request.organization).select_related("menu_item__category__menu").prefetch_related("options")
        branch_ids = accessible_branch_ids(self.request.user, self.request.organization)
        return queryset if branch_ids is None else queryset.filter(menu_item__category__menu__branch_id__in=branch_ids)

class OptionViewSet(TenantModelViewSet):
    serializer_class = OptionSerializer
    branch_relation = "group"
    branch_path = ("menu_item", "category", "menu", "branch")
    def get_queryset(self):
        queryset = Option.objects.filter(organization=self.request.organization).select_related("group__menu_item__category__menu")
        branch_ids = accessible_branch_ids(self.request.user, self.request.organization)
        return queryset if branch_ids is None else queryset.filter(group__menu_item__category__menu__branch_id__in=branch_ids)

class AddOnViewSet(TenantModelViewSet):
    serializer_class = AddOnSerializer
    branch_relation = "menu_item"
    branch_path = ("category", "menu", "branch")
    def get_queryset(self):
        queryset = AddOn.objects.filter(organization=self.request.organization).select_related("menu_item__category__menu")
        branch_ids = accessible_branch_ids(self.request.user, self.request.organization)
        return queryset if branch_ids is None else queryset.filter(menu_item__category__menu__branch_id__in=branch_ids)

class AvailabilityViewSet(TenantModelViewSet):
    serializer_class = AvailabilitySerializer
    branch_relation = "branch"
    def get_queryset(self):
        queryset = BranchItemAvailability.objects.filter(organization=self.request.organization).select_related("branch", "menu_item")
        branch_ids = accessible_branch_ids(self.request.user, self.request.organization)
        return queryset if branch_ids is None else queryset.filter(branch_id__in=branch_ids)
    def perform_create(self, serializer):
        branch_ids = accessible_branch_ids(self.request.user, self.request.organization)
        if branch_ids is not None and serializer.validated_data["branch"].id not in branch_ids:
            raise PermissionDenied("You cannot manage availability for this branch.")
        super().perform_create(serializer)

class PublicMenuByQRView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def get(self, request, token):
        table = RestaurantTable.objects.select_related("branch", "organization").filter(qr_token_hash=RestaurantTable.hash_token(token), is_active=True, branch__is_active=True, organization__is_active=True).first()
        if table is None:
            raise NotFound("QR code is invalid or inactive.")
        cache_key = f"public-menu:v1:{table.organization_id}:{table.branch_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response({"data": {"table": {"id": table.id, "number": table.number}, "branch": {"id": table.branch_id, "name": table.branch.name}, "menus": cached}, "meta": {"cached": True}})
        availability = BranchItemAvailability.objects.filter(branch=table.branch)
        items = MenuItem.objects.filter(is_active=True).prefetch_related("menuitemingredient_set__ingredient", "option_groups__options", "add_ons", Prefetch("branch_availability", queryset=availability))
        categories = Category.objects.filter(is_active=True).prefetch_related(Prefetch("items", queryset=items))
        menus = Menu.objects.filter(organization=table.organization, is_active=True).filter(Q(branch=table.branch) | Q(branch__isnull=True)).prefetch_related(Prefetch("categories", queryset=categories))
        from apps.operations.services import active_menus
        menus = active_menus(menus, table.branch)
        data = PublicMenuSerializer(menus, many=True, context={"branch": table.branch}).data
        cache.set(cache_key, data, timeout=30)
        return Response({"data": {"table": {"id": table.id, "number": table.number}, "branch": {"id": table.branch_id, "name": table.branch.name}, "menus": data}, "meta": {"cached": False}})
