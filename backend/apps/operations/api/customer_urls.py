from django.urls import path
from .views import CustomerReservationView
urlpatterns = [path("reservations/", CustomerReservationView.as_view(), name="customer-reservations")]
