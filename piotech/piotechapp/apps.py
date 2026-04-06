from django.apps import AppConfig


class PiotechappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'piotechapp'

    def ready(self):
        import piotechapp.signals
