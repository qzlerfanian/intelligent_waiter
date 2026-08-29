from .base import *  # noqa: F403
from django.core.exceptions import ImproperlyConfigured
if len(SECRET_KEY) < 32 or "change-me" in SECRET_KEY or SECRET_KEY == "unsafe-local-only":
    raise ImproperlyConfigured("APP_SECRET_KEY must be a strong secret in production.")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = [value for value in os.getenv("APP_CSRF_TRUSTED_ORIGINS", "").split(",") if value]
DATABASES["default"].update({"CONN_MAX_AGE": 60, "CONN_HEALTH_CHECKS": True})
