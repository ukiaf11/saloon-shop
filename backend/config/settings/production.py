from .base import *

DEBUG = False

SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
# Railway's healthcheck calls the container with this Host header. Without it
# Django answers 400 and the platform marks every deploy as failed.
ALLOWED_HOSTS += ["healthcheck.railway.app"]

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")

# --- Transport security ---------------------------------------------------

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Platform healthchecks call the container over plain HTTP from inside the
# network. Redirecting them to HTTPS returns a 301, which the platform reads as
# unhealthy. Only the dependency-free liveness probe is exempt.
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
SERVE_MEDIA = env.bool("SERVE_MEDIA", default=True)
MEDIA_ROOT = env("MEDIA_ROOT", default=str(BASE_DIR / "media"))

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
