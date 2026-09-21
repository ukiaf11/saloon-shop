"""Root test configuration.

The important thing here is the cache isolation. Several tests assert on cache
state, and the natural way to write that is `cache.clear()` -- but against the
configured Redis that is a FLUSHDB of db 0, which is also the Celery broker.
Running the suite while the dev stack is up would silently delete queued tasks.

Forcing every test onto locmem removes the footgun entirely: no test can reach
the real Redis, whatever it does.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_cache(settings):
    """Point the cache at locmem for every test, isolated per test."""
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-isolated",
        }
    }
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _test_encryption_key(settings):
    """Give every test a fixed field-encryption key.

    pytest-django forces settings.DEBUG = False during tests, so common.crypto
    takes its production branch and demands a real key. Without this the suite
    passes only on machines that happen to have a .env on disk -- which is how
    it passed locally and failed in CI.

    A fixed key also keeps ciphertext reproducible within a run, and it is
    obviously not a production value.
    """
    settings.FIELD_ENCRYPTION_KEY = "c2Fsb29uLXRlc3Qta2V5LW5vdC1wcm9kdWN0aW9uISE="


@pytest.fixture(autouse=True)
def _never_use_real_broker(settings):
    """Celery tasks run inline in tests; nothing should reach a real broker."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
