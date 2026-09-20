import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("salon")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# The daily campaign task runs at midnight Asia/Kolkata. It is never the only
# guarantee -- promotions.CampaignProvisioner also creates today's campaign
# lazily on first request, and both paths are idempotent against
# UNIQUE (salon_id, campaign_date). See REQUIREMENTS.md 3.5.
app.conf.beat_schedule = {
    "close-and-open-daily-campaign": {
        "task": "tasks.campaigns.close_and_open_daily_campaign",
        "schedule": crontab(hour=0, minute=0),
    },
    "expire-stale-reservations": {
        "task": "tasks.campaigns.expire_stale_reservations",
        "schedule": crontab(minute="*/2"),
    },
    "retry-pending-refunds": {
        "task": "tasks.refunds.retry_pending_refunds",
        "schedule": crontab(minute="*"),
    },
    "reconcile-payments": {
        "task": "tasks.payments.reconcile_payments",
        "schedule": crontab(minute="*/15"),
    },
    "expire-coupons": {
        "task": "tasks.coupons.expire_coupons",
        "schedule": crontab(hour=1, minute=0),
    },
}


@app.task(bind=True, name="tasks.heartbeat")
def heartbeat(self) -> str:
    """Proves broker -> worker -> beat wiring end to end."""
    return "ok"
