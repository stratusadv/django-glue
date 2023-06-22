from django.conf import settings as user_settings
from django_glue import settings as default_settings


class DjangoGlueSettings:
    def __getattr__(self, name):
        if hasattr(user_settings, name):
            return getattr(user_settings, name)

        if hasattr(default_settings, name):
            return getattr(default_settings, name)

        raise f'No attribute {name} found in settings.'


settings = DjangoGlueSettings()