from django.conf import settings as django_settings
from django_glue import settings as django_glue_default_settings


class Settings:
    def __getattr__(self, name):
        if hasattr(django_settings, name):
            return getattr(django_settings, name)

        if hasattr(django_glue_default_settings, name):
            return getattr(django_glue_default_settings, name)

        raise f'No attribute {name} found in settings.'


settings = Settings()
