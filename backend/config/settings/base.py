import os
from pathlib import Path
import dj_database_url
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parents[2]
SECRET_KEY = os.getenv("APP_SECRET_KEY", "unsafe-local-only")
DEBUG = False
ALLOWED_HOSTS = [x for x in os.getenv("APP_ALLOWED_HOSTS", "localhost").split(",") if x]
INSTALLED_APPS = ["django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "corsheaders", "rest_framework", "rest_framework_simplejwt.token_blacklist", "apps.core", "apps.identity", "apps.organizations", "apps.branches", "apps.tables", "apps.menus", "apps.customers", "apps.orders", "apps.payments", "apps.operations", "apps.staff", "apps.conversations", "apps.ai"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "corsheaders.middleware.CorsMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware"]
MIDDLEWARE.insert(1, "shared.observability.CorrelationAndMetricsMiddleware")
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
DATABASES = {"default": dj_database_url.config(default="postgresql://baran:baran@localhost:5432/baran", conn_max_age=60)}
AUTH_PASSWORD_VALIDATORS = [{"NAME": f"django.contrib.auth.password_validation.{name}"} for name in ["UserAttributeSimilarityValidator", "MinimumLengthValidator", "CommonPasswordValidator", "NumericPasswordValidator"]]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "identity.User"
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": ["shared.tenancy.authentication.TenantJWTAuthentication"], "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"], "EXCEPTION_HANDLER": "shared.api.exceptions.api_exception_handler", "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"], "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle", "rest_framework.throttling.UserRateThrottle"], "DEFAULT_THROTTLE_RATES": {"anon": "60/min", "user": "300/min"}}
SIMPLE_JWT = {"ROTATE_REFRESH_TOKENS": True, "BLACKLIST_AFTER_ROTATION": True, "UPDATE_LAST_LOGIN": True}
CORS_ALLOWED_ORIGINS = [x for x in os.getenv("APP_CORS_ALLOWED_ORIGINS", "").split(",") if x]
CORS_ALLOW_HEADERS = [*default_headers, "x-organization-id", "x-table-session", "idempotency-key", "x-request-id"]
CORS_EXPOSE_HEADERS = ["X-Request-ID"]
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
LOGGING = {"version": 1, "disable_existing_loggers": False, "formatters": {"json": {"()": "shared.logging.JsonFormatter"}}, "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}}, "root": {"handlers": ["console"], "level": os.getenv("APP_LOG_LEVEL", "INFO")}}
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL, "TIMEOUT": 60, "OPTIONS": {"socket_connect_timeout": 2, "socket_timeout": 2}}}
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_TIME_LIMIT = 120
CELERY_TASK_SOFT_TIME_LIMIT = 100
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {"dispatch-outbox": {"task": "apps.orders.tasks.dispatch_outbox", "schedule": 5.0}, "purge-expired-conversations": {"task": "apps.conversations.tasks.purge_expired_conversations", "schedule": 3600.0}}
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({"chat": os.getenv("RATE_CHAT", "20/min"), "checkout": os.getenv("RATE_CHECKOUT", "10/min"), "payment": os.getenv("RATE_PAYMENT", "10/min"), "reservation": os.getenv("RATE_RESERVATION", "5/min")})
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
AI_PROVIDER = os.getenv("AI_PROVIDER", "auto")
AI_MAX_TOOL_ROUNDS = int(os.getenv("AI_MAX_TOOL_ROUNDS", "4"))
METRICS_TOKEN = os.getenv("METRICS_TOKEN", "")
