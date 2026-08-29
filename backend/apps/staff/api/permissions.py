from rest_framework.permissions import BasePermission
from apps.organizations.models import Role

class IsRestaurantStaff(BasePermission):
    allowed_roles = {Role.OWNER, Role.ADMIN, Role.BRANCH_MANAGER, Role.CASHIER, Role.WAITER, Role.CHEF, Role.KITCHEN_STAFF}
    def has_permission(self, request, view):
        if request.organization is None:
            return False
        membership = request.user.memberships.filter(organization=request.organization, is_active=True).first()
        request.staff_membership = membership
        return membership is not None and membership.role in self.allowed_roles
