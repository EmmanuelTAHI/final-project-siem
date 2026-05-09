from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    verbose_name = "Notifications temps réel"

    def ready(self):
        from apps.notifications.signals import connect_signals
        connect_signals()
