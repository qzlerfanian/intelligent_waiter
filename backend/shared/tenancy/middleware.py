from uuid import UUID
from django.http import JsonResponse

class TenantContextMiddleware:
    """Resolve an explicitly selected tenant, never trust it as authorization."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organization = None
        raw_id = request.headers.get("X-Organization-ID")
        if raw_id:
            try:
                organization_id = UUID(raw_id)
            except ValueError:
                return JsonResponse({"error": {"code": "invalid_tenant", "message": "X-Organization-ID must be a UUID.", "details": {}}}, status=400)
            if request.user.is_authenticated:
                from apps.organizations.models import Organization
                request.organization = Organization.objects.filter(id=organization_id, is_active=True, memberships__user=request.user, memberships__is_active=True).first()
                if request.organization is None:
                    return JsonResponse({"error": {"code": "tenant_access_denied", "message": "You do not have access to this organization.", "details": {}}}, status=403)
        return self.get_response(request)
