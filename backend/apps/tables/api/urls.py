from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import ResolveQRView, RestaurantTableViewSet

router = DefaultRouter()
router.register("", RestaurantTableViewSet, basename="table")
urlpatterns = [path("resolve/<str:token>/", ResolveQRView.as_view(), name="qr-resolve"), path("", include(router.urls))]
