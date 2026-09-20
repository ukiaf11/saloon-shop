from django.apps import AppConfig


class SalonsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.salons"

    def ready(self) -> None:
        from apps.salons import signals  # noqa: F401  -- registers receivers
