from django.urls import path
from .views import CartLineCollectionView, CartLineDetailView, CartView, ConfirmOrderView, OrderDetailView

urlpatterns = [
    path("cart/", CartView.as_view(), name="customer-cart"),
    path("cart/items/", CartLineCollectionView.as_view(), name="customer-cart-items"),
    path("cart/items/<uuid:line_id>/", CartLineDetailView.as_view(), name="customer-cart-item-detail"),
    path("orders/confirm/", ConfirmOrderView.as_view(), name="customer-order-confirm"),
    path("orders/<uuid:order_id>/", OrderDetailView.as_view(), name="customer-order-detail"),
]
