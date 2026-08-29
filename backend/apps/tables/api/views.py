from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.tables.models import RestaurantTable
from apps.tables.services import rotate_qr_token
from shared.tenancy.permissions import CanManageRestaurantResources, HasTenantContext
from shared.tenancy.scopes import accessible_branch_ids
from .serializers import QRResolutionSerializer, RestaurantTableSerializer

class RestaurantTableViewSet(viewsets.ModelViewSet):
    serializer_class = RestaurantTableSerializer
    permission_classes = [IsAuthenticated, HasTenantContext, CanManageRestaurantResources]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    def get_queryset(self):
        queryset = RestaurantTable.objects.filter(organization=self.request.organization).select_related("branch")
        branch_ids = accessible_branch_ids(self.request.user, self.request.organization)
        return queryset if branch_ids is None else queryset.filter(branch_id__in=branch_ids)
    def perform_create(self, serializer):
        branch_ids = accessible_branch_ids(self.request.user, self.request.organization)
        if branch_ids is not None and serializer.validated_data["branch"].id not in branch_ids:
            raise PermissionDenied("You cannot manage this branch.")
        serializer.save()
    def perform_update(self, serializer):
        branch = serializer.validated_data.get("branch", serializer.instance.branch)
        branch_ids = accessible_branch_ids(self.request.user, self.request.organization)
        if branch_ids is not None and branch.id not in branch_ids:
            raise PermissionDenied("You cannot manage this branch.")
        serializer.save()
    @action(detail=True, methods=["post"])
    def rotate_qr(self, request, pk=None):
        return Response({"data": {"qr_token": rotate_qr_token(self.get_object())}, "meta": {}}, status=status.HTTP_200_OK)

class ResolveQRView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def get(self, request, token):
        table = RestaurantTable.objects.select_related("organization", "branch").filter(qr_token_hash=RestaurantTable.hash_token(token), is_active=True, branch__is_active=True, organization__is_active=True).first()
        if table is None:
            raise NotFound("QR code is invalid or inactive.")
        return Response({"data": QRResolutionSerializer(table).data, "meta": {}})
