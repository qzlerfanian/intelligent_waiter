from rest_framework.permissions import BasePermission
from apps.organizations.models import Role

class HasTenantContext(BasePermission):
    message = "Select an organization using X-Organization-ID."
    def has_permission(self, request, view):
        return request.organization is not None

class HasOrganizationRole(BasePermission):
    allowed_roles = ()
    def has_permission(self, request, view):
        organization = request.organization
        return bool(organization and request.user.memberships.filter(organization=organization, is_active=True, role__in=self.allowed_roles).exists())

class IsOrganizationAdmin(HasOrganizationRole):
    allowed_roles = (Role.OWNER, Role.ADMIN)

class CanManageRestaurantResources(HasOrganizationRole):
    allowed_roles = (Role.OWNER, Role.ADMIN, Role.BRANCH_MANAGER)
