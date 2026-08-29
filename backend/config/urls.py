from django.contrib import admin
from django.urls import include, path
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.core.api.urls")),
    path("api/v1/auth/", include("apps.identity.api.urls")),
    path("api/v1/organizations/", include("apps.organizations.api.urls")),
    path("api/v1/tables/", include("apps.tables.api.urls")),
    path("api/v1/menus/", include("apps.menus.api.urls")),
    path("api/v1/customer/", include("apps.customers.api.urls")),
    path("api/v1/customer/", include("apps.orders.api.urls")),
    path("api/v1/customer/", include("apps.payments.api.urls")),
    path("api/v1/operations/", include("apps.operations.api.urls")),
    path("api/v1/customer/", include("apps.operations.api.customer_urls")),
    path("api/v1/staff/", include("apps.staff.api.urls")),
    path("api/v1/customer/chat/", include("apps.conversations.api.urls")),
]
