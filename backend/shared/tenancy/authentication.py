from uuid import UUID
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication

class TenantJWTAuthentication(JWTAuthentication):
    """Authenticate first, then resolve tenant through an active membership."""

    def authenticate(self, request):
        request.organization = None
        authenticated = super().authenticate(request)
        if authenticated is None:
            return None
        user, token = authenticated
        raw_id = request.headers.get("X-Organization-ID")
        if not raw_id:
            return user, token
        try:
            organization_id = UUID(raw_id)
        except ValueError as exc:
            raise AuthenticationFailed("X-Organization-ID must be a UUID.", code="invalid_tenant") from exc
        from apps.organizations.models import Organization
        request.organization = Organization.objects.filter(id=organization_id, is_active=True, memberships__user=user, memberships__is_active=True).first()
        if request.organization is None:
            raise PermissionDenied("You do not have access to this organization.", code="tenant_access_denied")
        return user, token
