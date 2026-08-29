from django.urls import path

from .views import CustomerInvoiceView, CustomerPaymentCollectionView, MockGatewayConfirmView

urlpatterns = [
    path("payments/", CustomerPaymentCollectionView.as_view(), name="customer-payments"),
    path("payments/<uuid:payment_id>/mock-confirm/", MockGatewayConfirmView.as_view(), name="mock-payment-confirm"),
    path("orders/<uuid:order_id>/invoice/", CustomerInvoiceView.as_view(), name="customer-invoice"),
]

