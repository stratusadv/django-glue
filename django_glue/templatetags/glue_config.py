import json

from django_glue.conf import settings
from django_glue.templatetags.django_glue import register


@register.simple_tag()
def django_glue_client_type_config():
    client_config = {}
    for type_name, type_config in settings.DJANGO_GLUE_TYPE_CONFIG.items():
        client_config[type_name] = type_config.get(
            'client',
            type_config['server'].split('.')[-1]
        )

    return json.dumps(client_config)
