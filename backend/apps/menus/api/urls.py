from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import AddOnViewSet, AvailabilityViewSet, CategoryViewSet, IngredientViewSet, MenuItemViewSet, MenuViewSet, OptionGroupViewSet, OptionViewSet, PublicMenuByQRView

router = DefaultRouter()
router.register("catalogs", MenuViewSet, basename="menu")
router.register("categories", CategoryViewSet, basename="category")
router.register("ingredients", IngredientViewSet, basename="ingredient")
router.register("items", MenuItemViewSet, basename="menu-item")
router.register("option-groups", OptionGroupViewSet, basename="option-group")
router.register("options", OptionViewSet, basename="option")
router.register("add-ons", AddOnViewSet, basename="add-on")
router.register("availability", AvailabilityViewSet, basename="availability")
urlpatterns = [path("public/<str:token>/", PublicMenuByQRView.as_view(), name="public-menu"), path("", include(router.urls))]
