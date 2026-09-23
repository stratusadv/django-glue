from django.apps import AppConfig
from django.core.checks import register


class DjangoGlueConfig(AppConfig):
    name = 'django_glue'
    verbose_name = 'Django Glue'

    def ready(self) -> None:
        from django_glue.glue.component_discovery import autodiscover_components
        from django_glue.glue.component_registry import check_component_tag_names
        from django_glue.middleware import check_glue_view_middleware

        autodiscover_components()
        register(check_component_tag_names)
        register(check_glue_view_middleware)
