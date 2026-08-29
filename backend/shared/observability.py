import contextvars
import re
import time
import uuid
from django.core.cache import cache

request_id_context = contextvars.ContextVar("request_id", default="-")

class CorrelationAndMetricsMiddleware:
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID", "")
        if not re.fullmatch(r"[A-Za-z0-9._-]{8,80}", request_id): request_id = uuid.uuid4().hex
        request.request_id = request_id; token = request_id_context.set(request_id); started = time.monotonic()
        try:
            response = self.get_response(request)
            route = getattr(getattr(request, "resolver_match", None), "route", None) or "unmatched"
            safe_route = re.sub(r"[^A-Za-z0-9_.-]", "_", route)[:120]
            try:
                key = f"metrics:http:{request.method}:{response.status_code}:{safe_route}"
                cache.add(key, 0, timeout=None); cache.incr(key)
                cache.add("metrics:http_total", 0, timeout=None); cache.incr("metrics:http_total")
                if response.status_code >= 500:
                    cache.add("metrics:http_5xx_total", 0, timeout=None); cache.incr("metrics:http_5xx_total")
                cache.set("metrics:last_request_duration_ms", round((time.monotonic() - started) * 1000, 2), timeout=None)
            except Exception:
                pass
            response["X-Request-ID"] = request_id
            return response
        finally: request_id_context.reset(token)
