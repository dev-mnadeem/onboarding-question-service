from django.apps import AppConfig


class UserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "user"

    def ready(self):
        # Importing the module registers the post_save receiver.
        from user import signals  # noqa: F401
