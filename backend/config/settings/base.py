"""Settings shared by every environment.

Environment-specific modules (local / staging / production) import * from here
and then override. Nothing secret is ever defaulted to a usable value: secrets
must come from the environment, and production refuses to boot without them.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env()
env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-override-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# --- Applications ---------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

# django.contrib.admin is deliberately absent: the admin surface is a custom
# Next.js app (REQUIREMENTS.md 8.4). Django admin is never exposed in production.

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "django_celery_beat",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.salons",
    "apps.catalog",
    "apps.customers",
    "apps.orders",
    "apps.payments",
    "apps.promotions",
    "apps.coupons",
    "apps.refunds",
    "apps.analytics",
    "apps.content",
    "apps.audit",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "common.middleware.RequestIdMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
# WSGI only, deliberately. Vercel serves the ASGI app whenever ASGI_APPLICATION
# is set, with no reliable override, and nothing here needs ASGI.
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database -------------------------------------------------------------

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://salon:salon@localhost:5432/salon",
    ),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = False  # transactions are explicit
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.AdminUser"

# --- Cache / Celery -------------------------------------------------------

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    },
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TIMEZONE = "Asia/Kolkata"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# --- Passwords ------------------------------------------------------------

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- I18N / time ----------------------------------------------------------

LANGUAGE_CODE = "en-in"
# Storage is UTC; campaign_date is resolved in the salon's timezone explicitly
# by the promotions layer rather than implicitly at read time.
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
SALON_TIMEZONE = env("SALON_TIMEZONE", default="Asia/Kolkata")

# --- Static / media -------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- DRF ------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "common.exceptions.api_exception_handler",
    # Fails open if the cache is down -- see common/throttling.py for the trade.
    "DEFAULT_THROTTLE_CLASSES": [
        "common.throttling.ResilientScopedRateThrottle",
    ],
    # Tuned against real traffic post-launch; these are the spec's starting
    # values (REQUIREMENTS.md 3.6).
    "DEFAULT_THROTTLE_RATES": {
        "public_read": "120/min",
        "quote": "30/min",
        "order_create": "10/min",
        "otp_request": "3/10min",
        "payment_verify": "10/min",
        "coupon_lookup": "30/min",
        # Per IP, and only a first line: the real brute-force control is the
        # database-backed account lockout in apps.accounts.services, because
        # this throttle fails open when the cache is down.
        "admin_login": "10/15min",
        "upi_claim": "10/min",
        "owner": "300/min",
    },
    "UNAUTHENTICATED_USER": None,
}

# --- CORS -----------------------------------------------------------------

# django-cors-headers' default allowlist does not include Idempotency-Key, so
# without this the browser rejects the preflight for POST /orders and the call
# never leaves the page -- while the quote, which sends no such header,
# succeeds. Allowed origins themselves are set per environment.
from corsheaders.defaults import default_headers  # noqa: E402

CORS_ALLOW_HEADERS = (*default_headers, "idempotency-key")


# --- Field encryption -----------------------------------------------------

# Protects the daily campaign seed and winning positions at rest. Outside DEBUG
# this must be set, or common.crypto refuses to run -- see that module.
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", default="")


# --- Business defaults ----------------------------------------------------

CAMPAIGN_RESERVATION_TTL_SECONDS = env.int("CAMPAIGN_RESERVATION_TTL_SECONDS", default=600)

# A UPI QR payment is verified by a person, not a webhook, so its draw entry is
# held far longer than a gateway checkout's: long enough for the owner to check
# their UPI app, and in practice ended by the nightly close of the day anyway.
UPI_CLAIM_HOLD_SECONDS = env.int("UPI_CLAIM_HOLD_SECONDS", default=36 * 3600)
# Unverified claims one network may have waiting at once. Each holds a draw
# place, so without a cap one script could fill the day with fake references.
UPI_CLAIM_MAX_PENDING_PER_IP = env.int("UPI_CLAIM_MAX_PENDING_PER_IP", default=3)
# After the owner removes the QR, customers who were already mid-payment may
# still send their reference for this long.
UPI_CLAIM_GRACE_AFTER_QR_REMOVED_HOURS = 48

# --- Owner panel sessions and login protection -------------------------------

ADMIN_SESSION_TTL_HOURS = env.int("ADMIN_SESSION_TTL_HOURS", default=12)
# Consecutive failures before an account locks, and for how long.
LOGIN_MAX_FAILURES = 5
LOGIN_LOCKOUT_MINUTES = 15
# Failures from one IP, across all accounts, within the lockout window.
LOGIN_IP_MAX_FAILURES = 20
# Behind Vercel the client address arrives in X-Real-IP, which the edge sets
# itself; REMOTE_ADDR is the proxy. Trust the header only where that is true.
TRUST_X_REAL_IP = env.bool("TRUST_X_REAL_IP", default=False)
COUPON_TOKEN_BYTES = 32  # 256 bits, well above the 128-bit floor
LUCKY_SEED_BYTES = 32

# --- Logging --------------------------------------------------------------

LOG_LEVEL = env("LOG_LEVEL", default="INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "common.logging.RequestIdFilter"},
    },
    "formatters": {
        "json": {"()": "common.logging.JsonFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["request_id"],
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.db.backends": {"level": "WARNING", "propagate": True},
    },
}
