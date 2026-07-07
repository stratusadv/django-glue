def get_subject_type_to_proxy_class():
    from django_glue.proxies import (
        GlueModelInstanceProxy,
        GlueFormProxy,
        GlueQuerySetProxy,
        GlueTemplateProxy,
        GlueFunctionProxy,
    )
    return {
        'model': GlueModelInstanceProxy,
        'querySet': GlueQuerySetProxy,
        'form': GlueFormProxy,
        'template': GlueTemplateProxy,
        'function': GlueFunctionProxy,
    }
