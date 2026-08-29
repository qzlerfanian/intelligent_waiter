from rest_framework import mixins, serializers, viewsets
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from rest_framework.exceptions import PermissionDenied
from apps.branches.models import BranchAssignment
from apps.branches.models import Branch
from apps.organizations.models import Membership, Organization
from shared.tenancy.permissions import HasTenantContext, IsOrganizationAdmin
from shared.tenancy.permissions import CanManageRestaurantResources
from shared.tenancy.scopes import accessible_branch_ids
from .serializers import BranchSerializer, MembershipSerializer, OrganizationSerializer

class OrganizationViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return Organization.objects.filter(memberships__user=self.request.user, memberships__is_active=True).distinct()
    def perform_update(self, serializer):
        if not serializer.instance.memberships.filter(user=self.request.user, is_active=True, role__in=["owner", "admin"]).exists():
            raise PermissionDenied("Only organization administrators can edit organization details.")
        serializer.save()

class MembershipViewSet(viewsets.ModelViewSet):
    serializer_class = MembershipSerializer
    permission_classes = [IsAuthenticated, HasTenantContext, IsOrganizationAdmin]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    def get_queryset(self):
        return Membership.objects.filter(organization=self.request.organization).select_related("user")
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        Organization.objects.select_for_update().get(pk=request.organization.pk)
        return super().create(request, *args, **kwargs)
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        Organization.objects.select_for_update().get(pk=request.organization.pk)
        return super().update(request, *args, **kwargs)
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        Organization.objects.select_for_update().get(pk=request.organization.pk)
        return super().destroy(request, *args, **kwargs)
    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)
    def perform_destroy(self, instance):
        if instance.role == "owner" and not self.request.user.memberships.filter(organization=instance.organization, role="owner", is_active=True).exists():
            raise PermissionDenied("Only an owner can remove an owner.")
        if instance.user_id == self.request.user.id:
            raise serializers.ValidationError("You cannot remove your own membership.")
        other_owner_exists = Membership.objects.filter(organization=instance.organization, role="owner", is_active=True).exclude(pk=instance.pk).exists()
        if instance.role == "owner" and not other_owner_exists:
            raise serializers.ValidationError("An organization must retain at least one active owner.")
        BranchAssignment.objects.filter(user=instance.user, branch__organization=instance.organization).delete()
        instance.delete()

class BranchViewSet(viewsets.ModelViewSet):
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated, HasTenantContext, IsOrganizationAdmin]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    def get_permissions(self):
        roles = CanManageRestaurantResources if self.request.method in ("GET", "HEAD", "OPTIONS") else IsOrganizationAdmin
        return [IsAuthenticated(), HasTenantContext(), roles()]
    def get_queryset(self):
        queryset = Branch.objects.filter(organization=self.request.organization)
        ids = accessible_branch_ids(self.request.user, self.request.organization)
        return queryset if ids is None else queryset.filter(pk__in=ids)
    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)
