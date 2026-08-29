from django.urls import path
from .views import ClaimSessionView, CustomerFavoriteCollectionView, CustomerFavoriteDetailView, CustomerLoyaltyView, CustomerOrderHistoryView, CustomerPrivacyEraseView, CustomerProfileView, CustomerReorderView, CurrentSessionView, SessionMenuView, StartSessionView

urlpatterns = [
    path("sessions/", StartSessionView.as_view(), name="customer-session-start"),
    path("session/", CurrentSessionView.as_view(), name="customer-session-current"),
    path("session/claim/", ClaimSessionView.as_view(), name="customer-session-claim"),
    path("menu/", SessionMenuView.as_view(), name="customer-session-menu"),
    path("account/profile/", CustomerProfileView.as_view(), name="customer-profile"),
    path("account/orders/", CustomerOrderHistoryView.as_view(), name="customer-order-history"),
    path("account/orders/<uuid:order_id>/reorder/", CustomerReorderView.as_view(), name="customer-reorder"),
    path("account/favorites/", CustomerFavoriteCollectionView.as_view(), name="customer-favorites"),
    path("account/favorites/<uuid:item_id>/", CustomerFavoriteDetailView.as_view(), name="customer-favorite-detail"),
    path("account/loyalty/", CustomerLoyaltyView.as_view(), name="customer-loyalty"),
    path("account/privacy/erase/", CustomerPrivacyEraseView.as_view(), name="customer-privacy-erase"),
]
