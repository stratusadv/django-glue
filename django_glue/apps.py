from django.apps import AppConfig
from django.core.checks import register


class DjangoGlueConfig(AppConfig):
    name = 'django_glue'
    verbose_name = 'Django Glue'

    def ready(self) -> None:
        from django_glue.middleware import check_glue_view_middleware

        register(check_glue_view_middleware)
