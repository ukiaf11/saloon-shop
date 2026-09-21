from .base import *

DEBUG = False

SECRET_KEY = env("DJANGO_SECRET_KEY")

# Vercel sets VERCEL=1 in both the build and the runtime.
ON_VERCEL = env.bool("VERCEL", default=False)

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
if ON_VERCEL:
    # The production alias and this deployment's own URL. Both are injected by
    # the platform, so a preview or a promoted deployment answers without a
    # settings change. Never a "*.vercel.app" wildcard: anyone can register a
    # look-alike subdomain there.
    for _var in ("VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_URL", "VERCEL_BRANCH_URL"):
        _host = env(_var, default="").strip()
        if _host and _host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(_host)
if not ALLOWED_HOSTS:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS is empty; refusing to serve any host.")

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")

# --- Transport security ---------------------------------------------------

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Container platforms probe health over plain HTTP from inside their network;
# a 301 there reads as unhealthy. Only the dependency-free liveness probe is
# exempt. (On Vercel every request already arrives as HTTPS.)
SECURE_REDIRECT_EXEMPT = [r"^healthz$"]
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False  # the admin SPA must read it to echo the header
CSRF_COOKIE_SAMESITE = "Lax"

PAYMENT_GATEWAY_MODE = env("PAYMENT_GATEWAY_MODE", default="live")

# The API speaks JSON only in production. DRF's browsable HTML API is a
# developer tool: it needs static files gunicorn does not serve, and it hands
# every visitor an interactive form for each endpoint.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

# Uploaded images (service photos, gallery), served by Django from a persistent
# volume until object storage is provisioned. Adequate for one salon's handful
# of images; moving to S3/R2 later is a settings change, not a code change.
# Django refuses to serve media outside DEBUG by default, so this is an
# explicit, documented choice rather than an accident.
# Off on Vercel: its function filesystem is read-only and per-instance, so an
# upload could never be served back. Uploads arrive with the admin phase and
# will need object storage (Vercel Blob or R2) then.
SERVE_MEDIA = env.bool("SERVE_MEDIA", default=not ON_VERCEL)
TRUST_X_REAL_IP = env.bool("TRUST_X_REAL_IP", default=ON_VERCEL)
MEDIA_ROOT = env("MEDIA_ROOT", default=str(BASE_DIR / "media"))

# --- Serverless database and cache ------------------------------------------

if ON_VERCEL:
    _db = DATABASES["default"]
    # Each invocation opens its own connection. Keeping one open across
    # requests leaks: a suspended instance never runs its idle timeout, and
    # Neon drops connections when its compute scales to zero.
    _db["CONN_MAX_AGE"] = 0
    _db["CONN_HEALTH_CHECKS"] = True
    # DATABASE_URL is Neon's PgBouncer pooler in transaction mode. Row locks
    # (SELECT ... FOR UPDATE) are fine there -- a transaction keeps one server
    # connection -- but server-side cursors outlive a transaction and break.
    _db["DISABLE_SERVER_SIDE_CURSORS"] = True
    # Neon refuses plaintext connections; guard against a URL without sslmode.
    _db.setdefault("OPTIONS", {}).setdefault("sslmode", "require")

# Redis when one is configured; otherwise Django's database cache on Postgres.
# NOT the in-memory cache: that is per instance, so a price change would clear
# only the instance that handled it while others served the stale price for up
# to 15 minutes, and throttle limits would multiply with instance count. The
# table is created by `createcachetable` in vercel_build.py.
_redis_url = env("REDIS_URL", default="").strip()
if _redis_url:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _redis_url,
        }
    }
elif ON_VERCEL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "django_cache",
            # The default of 300 would cull throttle histories under load.
            "OPTIONS": {"MAX_ENTRIES": 10000},
        }
    }

# --- Error monitoring -----------------------------------------------------

SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.1),
        send_default_pii=False,  # never ship customer PII to the tracker
        environment=env("ENVIRONMENT", default="production"),
    )
