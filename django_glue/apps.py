from django.apps import AppConfig
from django.core.checks import register


class DjangoGlueConfig(AppConfig):
    name = 'django_glue'
    verbose_name = 'Django Glue'

    def ready(self) -> None:
        from django_glue.glue.component.autodiscover import autodiscover_components
        from django_glue.glue.component.checks import check_component_tag_names

        autodiscover_components()
        register(check_component_tag_names)
