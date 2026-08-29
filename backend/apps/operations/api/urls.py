from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import CampaignViewSet, MenuScheduleViewSet, RecipeComponentViewSet, ReservationViewSet, StockItemViewSet
router = DefaultRouter()
router.register("campaigns", CampaignViewSet, basename="campaign")
router.register("menu-schedules", MenuScheduleViewSet, basename="menu-schedule")
router.register("stock", StockItemViewSet, basename="stock")
router.register("recipes", RecipeComponentViewSet, basename="recipe")
router.register("reservations", ReservationViewSet, basename="reservation")
urlpatterns = [path("", include(router.urls))]
