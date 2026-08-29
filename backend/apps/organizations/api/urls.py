from django.urls import path
from .views import BranchViewSet, MembershipViewSet, OrganizationViewSet

organizations = OrganizationViewSet.as_view({"get": "list", "post": "create"})
organization_detail = OrganizationViewSet.as_view({"get": "retrieve", "patch": "partial_update"})
members = MembershipViewSet.as_view({"get": "list", "post": "create"})
member_detail = MembershipViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"})
branches = BranchViewSet.as_view({"get": "list", "post": "create"})
branch_detail = BranchViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"})

urlpatterns = [
    path("", organizations, name="organization-list"),
    path("<uuid:pk>/", organization_detail, name="organization-detail"),
    path("members/", members, name="membership-list"),
    path("members/<uuid:pk>/", member_detail, name="membership-detail"),
    path("branches/", branches, name="branch-list"),
    path("branches/<uuid:pk>/", branch_detail, name="branch-detail"),
]
