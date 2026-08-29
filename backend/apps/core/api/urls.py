from django.urls import path
from .views import HealthView, MetricsView, ReadinessView

urlpatterns = [path("health/", HealthView.as_view(), name="health"), path("ready/", ReadinessView.as_view(), name="readiness"), path("metrics/", MetricsView.as_view(), name="metrics")]
