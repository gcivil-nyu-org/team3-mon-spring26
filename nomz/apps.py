from django.apps import AppConfig


class NomzConfig(AppConfig):
    name = 'nomz'

    def ready(self):
        from . import signals  # noqa: F401
