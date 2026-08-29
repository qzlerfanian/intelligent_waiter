from django.urls import path
from .views import StaffAnalyticsView, StaffCollectPaymentView, StaffContextView, StaffOrderDetailView, StaffOrderListView, StaffSummaryView

urlpatterns = [
    path("context/", StaffContextView.as_view(), name="staff-context"),
    path("orders/", StaffOrderListView.as_view(), name="staff-orders"),
    path("orders/summary/", StaffSummaryView.as_view(), name="staff-order-summary"),
    path("orders/<uuid:order_id>/", StaffOrderDetailView.as_view(), name="staff-order-detail"),
    path("orders/<uuid:order_id>/collect-payment/", StaffCollectPaymentView.as_view(), name="staff-collect-payment"),
    path("analytics/", StaffAnalyticsView.as_view(), name="staff-analytics"),
]
