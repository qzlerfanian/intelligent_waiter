from django.db import connection
from django.core.cache import cache
from django.http import HttpResponse
from django.conf import settings
from apps.orders.models import NotificationOutbox
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"data": {"status": "ok"}, "meta": {}})

class ReadinessView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def get(self, request):
        checks = {}
        try:
            with connection.cursor() as cursor: cursor.execute("SELECT 1"); cursor.fetchone()
            checks["database"] = "ok"
        except Exception: checks["database"] = "error"
        try: cache.set("readiness", "ok", 5); checks["redis"] = "ok" if cache.get("readiness") == "ok" else "error"
        except Exception: checks["redis"] = "error"
        ready = all(value == "ok" for value in checks.values())
        return Response({"data": {"status": "ready" if ready else "not_ready", "checks": checks}, "meta": {}}, status=200 if ready else 503)

class MetricsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def get(self, request):
        if settings.METRICS_TOKEN and request.headers.get("Authorization") != f"Bearer {settings.METRICS_TOKEN}":
            return Response(status=404)
        pending = NotificationOutbox.objects.filter(status="pending").count()
        lines = ["# HELP baran_outbox_pending Pending transactional events", "# TYPE baran_outbox_pending gauge", f"baran_outbox_pending {pending}", "# TYPE baran_http_requests_total counter", f"baran_http_requests_total {cache.get('metrics:http_total', 0)}", "# TYPE baran_http_5xx_total counter", f"baran_http_5xx_total {cache.get('metrics:http_5xx_total', 0)}", "# TYPE baran_last_request_duration_ms gauge", f"baran_last_request_duration_ms {cache.get('metrics:last_request_duration_ms', 0)}"]
        return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; version=0.0.4")
