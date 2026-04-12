from django.apps import AppConfig

class MessagingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "messaging"
    verbose_name = "Messaging"

    def ready(self) -> None:
        import messaging.tasks  # noqa: F401
